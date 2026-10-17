"""测试共用件：上传链路的真库环境、假解析器 / 假嵌入模型与轮询工具。

为什么单独一个模块而不是复制进每个测试文件：SonarCloud 的质量门禁对**新代码重复率**卡 3%，
两份几乎相同的 60 行夹具一提交就 18% —— 重复的夹具还会各自漂移（改一份忘另一份）。
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.api.document_controller import get_job_service
from app.db.init_db import initialize_database, load_sqlite_vec_extension
from app.db.orm import create_database_engine, create_session_factory
from app.main import app
from app.services.document_ingest_service import DocumentIngestService
from app.services.embedding_service import EmbeddingService
from app.services.ingest_job_service import IngestJobService

#: 测试用小维度：真 sqlite-vec、假模型，CI 既不下载 2.2 GB 也不调外部 API。
DIMENSION = 8
MODEL_NAME = "fake-embedding-model"
TERMINAL_STATUSES = {"succeeded", "failed"}


class FakeEmbeddingModel:
    """按批内顺序返回确定向量：query 落在 index 0，必然命中最先入库的片段。"""

    def embed(self, texts, batch_size=None):  # noqa: ARG002 - 签名对齐 fastembed
        for index, _ in enumerate(list(texts)):
            yield [float(index) + 1.0] * DIMENSION


def make_parser_patch(pages):
    """把 ParserFactory 换成返回固定页的假解析器（调用方负责 `patcher.stop()`）。"""
    patcher = patch("app.parsers.parser_factory.ParserFactory.get_parser")
    mock_get_parser = patcher.start()
    mock_parser = MagicMock()
    mock_parser.parse.return_value = pages
    mock_get_parser.return_value = mock_parser
    return patcher


def make_page(page_number: int, content: str) -> dict:
    return {
        "page_number": page_number,
        "content": content,
        "char_count": len(content),
        "parser_name": "FakeParser",
        "parser_version": "1.0.0",
        "metadata": {"source_type": "pdf"},
    }


@contextmanager
def upload_env(tmp_path, *, database_name: str = "upload.sqlite3"):
    """真临时库 + 真 sqlite-vec + 假嵌入模型；产出 (session_factory, ingest_service, embedding_service)。

    刻意**不**注册 `dependency_overrides` —— 每个用例自己用 `client_for` 装上指向本环境的
    job service；否则会误用生产单例（那会真的去建 `data/` 下的库）。
    """
    initialization = initialize_database(
        data_dir=tmp_path / "data",
        database_name=database_name,
        embedding_dimension=DIMENSION,
        sqlite_vec_loader=load_sqlite_vec_extension,
    )
    engine = create_database_engine(
        initialization.database_path,
        sqlite_vec_loader=load_sqlite_vec_extension,
    )
    session_factory = create_session_factory(engine)
    embedding_service = EmbeddingService(
        model_name=MODEL_NAME,
        dimension=DIMENSION,
        model_factory=lambda name: FakeEmbeddingModel(),  # noqa: ARG005 - 对齐 ModelFactory
        query_prefix="",
        passage_prefix="",
    )
    ingest_service = DocumentIngestService(
        session_factory=session_factory,
        embedding_service=embedding_service,
        embedding_model=MODEL_NAME,
        embedding_dimension=DIMENSION,
    )
    try:
        yield session_factory, ingest_service, embedding_service
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def client_for(job_service: IngestJobService) -> TestClient:
    """装上指向测试环境的 job service（provider 单例等仍走生产装配）。"""
    app.dependency_overrides[get_job_service] = lambda: job_service
    return TestClient(app)


def poll_until_terminal(client: TestClient, job_id: str, timeout: float = 15.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        payload = client.get(f"/api/documents/jobs/{job_id}").json()["data"]
        if payload["status"] in TERMINAL_STATUSES:
            return payload
        time.sleep(0.02)
    raise AssertionError(f"任务 {job_id} 没有在 {timeout}s 内结束")


def upload(client: TestClient, filename: str = "cours.pdf", content: bytes = b"%PDF-1.4"):
    return client.post(
        "/api/documents/upload",
        files={"file": (filename, content, "application/octet-stream")},
    )
