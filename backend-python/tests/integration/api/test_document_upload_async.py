"""
上传异步化端到端：202 受理 → 轮询进度 → 完成后立即可检索。

用真 sqlite-vec + 假嵌入模型（CI 既不下载模型、也不调外部 API）。
这里验证的正是"上传不再让客户端干等"这件事：
用**真线程池** + 一个能被卡住的摄取服务，证明上传请求在摄取完成**之前**就返回了。

对应规格：docs/specs/us-stage1-upload-async.md
"""
import threading
import time

import pytest

from app.db.models import IngestJobModel
from app.rag.retriever import Retriever
from app.repositories.embedding_repository import EmbeddingRepository
from app.services.ingest_job_service import IngestJobService
from tests.support.upload_harness import (
    DIMENSION,
    MODEL_NAME,
    TERMINAL_STATUSES,
    client_for,
    make_page,
    make_parser_patch,
    poll_until_terminal,
    upload,
    upload_env as build_upload_env,
)

pytestmark = [pytest.mark.integration]


class BlockingIngestService:
    """摄取一开始就卡住，直到测试放行 —— 用来证明"上传不等它"。"""

    def __init__(self, inner, started: threading.Event, release: threading.Event) -> None:
        self.inner = inner
        self.started = started
        self.release = release

    def ingest_document(self, filename, content, *, on_progress=None, **kwargs):
        self.started.set()
        if not self.release.wait(timeout=10):
            raise AssertionError("摄取没有被放行，测试可能挂住了")
        return self.inner.ingest_document(
            filename, content, on_progress=on_progress, **kwargs
        )


@pytest.fixture
def upload_env(tmp_path):
    """真库 + 真摄取服务（假嵌入模型）。

    这里**不**注册 `dependency_overrides` —— 每个用例自己用 `client_for` 装上
    指向本环境的 job service；否则会误用生产单例（那会真的去建 data/ 下的库）。
    """
    with build_upload_env(tmp_path, database_name="upload.sqlite3") as harness:
        yield harness


# ========== AC1：受理不等摄取 ==========


def test_upload_returns_202_while_ingestion_is_still_running(upload_env):
    session_factory, inner, _ = upload_env
    started = threading.Event()
    release = threading.Event()
    blocking = BlockingIngestService(inner, started, release)

    patcher = make_parser_patch([make_page(1, "premier paragraphe")])
    try:
        client = client_for(
            IngestJobService(session_factory=session_factory, ingest_service=blocking)
        )

        response = upload(client)

        assert response.status_code == 202, "上传必须在摄取完成前返回"
        assert started.wait(timeout=5), "摄取应该已经在后台跑起来了"
        assert not release.is_set(), "能走到这一行，就说明上传没等摄取结束"

        job_id = response.json()["data"]["job_id"]
        payload = client.get(f"/api/documents/jobs/{job_id}").json()["data"]
        assert payload["status"] in {"queued", "running"}
        assert payload["filename"] == "cours.pdf"

        release.set()
        finished = poll_until_terminal(client, job_id)
        assert finished["error"] is None, finished["error"]
        assert finished["status"] == "succeeded"
    finally:
        release.set()
        patcher.stop()


# ========== AC2 / AC3：轮询到终态，数据立即可检索 ==========


def test_polling_reaches_succeeded_and_chunks_are_retrievable(upload_env):
    session_factory, ingest_service, embedding_service = upload_env
    patcher = make_parser_patch(
        [make_page(1, "premier paragraphe du cours"), make_page(2, "deuxieme paragraphe")]
    )
    try:
        client = client_for(
            IngestJobService(session_factory=session_factory, ingest_service=ingest_service)
        )
        response = upload(client)
        assert response.status_code == 202

        job_id = response.json()["data"]["job_id"]
        payload = poll_until_terminal(client, job_id)

        assert payload["error"] is None, payload["error"]
        assert payload["status"] == "succeeded"
        assert payload["progress"] == 1.0
        assert payload["result"]["filename"] == "cours.pdf"
        assert payload["result"]["total_pages"] == 2
        assert payload["result"]["document_units_count"] == 2
        assert payload["result"]["chunks_created"] >= 1
        assert payload["result"]["document_id"]

        with session_factory() as session:
            hits = Retriever(embedding_service, top_k=3).retrieve(
                EmbeddingRepository(session, embedding_dimension=DIMENSION),
                "premier paragraphe",
            )
        assert hits, "摄取完成后必须立刻能检索到"
    finally:
        patcher.stop()


# ========== AC4：失败走 job，不走上传响应 ==========


def test_failed_ingestion_is_reported_through_the_job(upload_env):
    session_factory, _, _ = upload_env

    class ExplodingIngestService:
        def ingest_document(self, filename, content, *, on_progress=None, **kwargs):
            raise ValueError("解析器无法解析该文件")

    client = client_for(
        IngestJobService(
            session_factory=session_factory, ingest_service=ExplodingIngestService()
        )
    )

    response = upload(client)

    assert response.status_code == 202, "摄取失败不该让上传请求变成 5xx"

    job_id = response.json()["data"]["job_id"]
    payload = poll_until_terminal(client, job_id)

    assert payload["status"] == "failed"
    assert "解析器无法解析该文件" in payload["error"]
    assert payload["result"] is None


# ========== AC5：未知任务 ==========


def test_unknown_job_id_returns_404(upload_env):
    session_factory, ingest_service, _ = upload_env
    client = client_for(
        IngestJobService(session_factory=session_factory, ingest_service=ingest_service)
    )

    response = client.get("/api/documents/jobs/does-not-exist")

    assert response.status_code == 404


# ========== AC9：同步校验照旧，且不留 job ==========


def test_rejected_upload_returns_400_without_creating_a_job(upload_env):
    session_factory, ingest_service, _ = upload_env
    client = client_for(
        IngestJobService(session_factory=session_factory, ingest_service=ingest_service)
    )

    response = upload(client, filename="slides.ppt", content=b"content")

    assert response.status_code == 400
    assert "暂不支持" in response.json()["detail"]

    with session_factory() as session:
        assert session.query(IngestJobModel).count() == 0, "被拒的上传不该留下 job"
