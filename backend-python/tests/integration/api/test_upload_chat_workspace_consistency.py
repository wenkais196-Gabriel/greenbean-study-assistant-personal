"""
R1-2 验收：上传与会话写入**同一个** workspace_id，且"按 workspace 过滤"不再滤空。

对应 GitHub issue #11（`T-R1-2.1`）与 #13（`T-R1-2.3`），契约 `docs/specs/r1-contracts.md` C6。

为什么必须**查库**断言：`GET /api/documents` 的响应体里没有 `workspace_id` 字段，
从响应里"看出来"等于什么都没验证。这里直接读 `document_records.workspace_id`。

环境：真临时库 + 真 sqlite-vec + 假解析器 / 假嵌入模型（CI 不下载模型、不调外部 API）。
"""
import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.document_controller import get_job_service
from app.config.settings import DEFAULT_WORKSPACE_ID
from app.db.init_db import initialize_database, load_sqlite_vec_extension
from app.db.orm import create_database_engine, create_session_factory
from app.main import app
from app.repositories.document_repository import DocumentRepository
from app.services import chat_session_service
from app.services.document_ingest_service import DocumentIngestService
from app.services.embedding_service import EmbeddingService
from app.services.ingest_job_service import IngestJobService
from app.tools.adapters import ProductionChunkSearcher

pytestmark = [pytest.mark.integration]

DIMENSION = 8
MODEL_NAME = "fake-embedding-model"
TERMINAL_STATUSES = {"succeeded", "failed"}


class FakeEmbeddingModel:
    """按批内顺序返回确定向量：query 落在 index 0，必然命中最先入库的片段。"""

    def embed(self, texts, batch_size=None):
        for index, _ in enumerate(list(texts)):
            yield [float(index) + 1.0] * DIMENSION


def make_parser_patch(pages):
    """把 ParserFactory 换成返回固定页的假解析器。"""
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


@pytest.fixture
def upload_env(tmp_path):
    """真库 + 真摄取服务（假嵌入模型）；不注册 `dependency_overrides`，避免误用生产单例。"""
    initialization = initialize_database(
        data_dir=tmp_path / "data",
        database_name="workspace.sqlite3",
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
        model_factory=lambda name: FakeEmbeddingModel(),
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


def upload(client: TestClient, filename: str = "cours_agile.pdf", content: bytes = b"%PDF-1.4"):
    return client.post(
        "/api/documents/upload",
        files={"file": (filename, content, "application/octet-stream")},
    )


# ========== T-R1-2.1：上传落库不再写空串 ==========


@pytest.mark.us("R1-2")
def test_upload_without_workspace_persists_the_default_workspace(upload_env):
    """请求里没指定工作区 → `document_records.workspace_id` 是 `"default"`，不是 `""`。"""
    session_factory, ingest_service, _ = upload_env
    patcher = make_parser_patch([make_page(1, "premier paragraphe du cours")])
    try:
        client = client_for(
            IngestJobService(session_factory=session_factory, ingest_service=ingest_service)
        )
        response = upload(client)
        assert response.status_code == 202

        job_id = response.json()["data"]["job_id"]
        payload = poll_until_terminal(client, job_id)
        assert payload["status"] == "succeeded", payload["error"]

        with session_factory() as session:
            records = DocumentRepository(session).list_all()

        assert len(records) == 1
        assert records[0].workspace_id == "default"
        assert records[0].workspace_id == DEFAULT_WORKSPACE_ID
    finally:
        patcher.stop()


@pytest.mark.us("R1-2")
def test_upload_and_chat_share_one_constant(upload_env):
    """上传侧与会话侧的缺省工作区来自**同一份常量** —— 不是两处字面量恰好相等。

    常量本身用身份断言（`is`）：两边各写一个 `"default"` 也能 `==`，但那正是本 bug 的成因。
    从 SQLite 读回来的字符串必然是新对象，因此落库值只能用 `==` 比 —— 比较的是值，不是身份。
    """
    assert chat_session_service.DEFAULT_WORKSPACE_ID is DEFAULT_WORKSPACE_ID

    session_factory, ingest_service, _ = upload_env
    patcher = make_parser_patch([make_page(1, "contenu")])
    try:
        client = client_for(
            IngestJobService(session_factory=session_factory, ingest_service=ingest_service)
        )
        job_id = upload(client).json()["data"]["job_id"]
        assert poll_until_terminal(client, job_id)["status"] == "succeeded"

        with session_factory() as session:
            stored = DocumentRepository(session).list_all()[0].workspace_id

        assert stored == chat_session_service.DEFAULT_WORKSPACE_ID
        assert stored == "default", "落库值必须可读可查，不是空串"
    finally:
        patcher.stop()


# ========== T-R1-2.3：按 workspace 检索不再滤空 ==========


@pytest.mark.us("R1-2")
def test_retrieval_by_default_workspace_finds_the_uploaded_document(upload_env):
    """上传（未指定工作区）→ 按 `"default"` 检索能召回，按不存在的工作区检索为 0 条。

    两条断言必须成对出现：只断言"命中 ≥ 1"的话，一个**忽略过滤参数**的实现也能通过。
    """
    session_factory, ingest_service, embedding_service = upload_env
    patcher = make_parser_patch(
        [make_page(1, "premier paragraphe du cours"), make_page(2, "deuxieme paragraphe")]
    )
    try:
        client = client_for(
            IngestJobService(session_factory=session_factory, ingest_service=ingest_service)
        )
        job_id = upload(client).json()["data"]["job_id"]
        payload = poll_until_terminal(client, job_id)
        assert payload["status"] == "succeeded", payload["error"]

        searcher = ProductionChunkSearcher(
            session_factory=session_factory,
            embedding_service=embedding_service,
            embedding_dimension=DIMENSION,
        )

        hits = searcher.search(
            query="premier paragraphe", workspace_id=DEFAULT_WORKSPACE_ID, top_k=5
        )
        assert hits, "按缺省工作区检索必须能召回刚上传的文档（空结果说明过滤滤空了）"

        with session_factory() as session:
            for hit in hits:
                document = DocumentRepository(session).get_by_id(hit["document_id"])
                assert document is not None
                assert document.workspace_id == DEFAULT_WORKSPACE_ID

        assert searcher.search(query="premier paragraphe", workspace_id="no-such-workspace") == []
    finally:
        patcher.stop()
