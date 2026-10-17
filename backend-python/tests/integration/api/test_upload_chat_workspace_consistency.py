"""
R1-2 验收：上传与会话写入**同一个** workspace_id，且"按 workspace 过滤"不再滤空。

对应 GitHub issue #11（`T-R1-2.1`）与 #13（`T-R1-2.3`），契约 `docs/specs/r1-contracts.md` C6。

为什么必须**查库**断言：`GET /api/documents` 的响应体里没有 `workspace_id` 字段，
从响应里"看出来"等于什么都没验证。这里直接读 `document_records.workspace_id`。

环境：真临时库 + 真 sqlite-vec + 假解析器 / 假嵌入模型（CI 不下载模型、不调外部 API）。
"""
import pytest

from app.config.settings import DEFAULT_WORKSPACE_ID
from app.repositories.document_repository import DocumentRepository
from app.services import chat_session_service
from app.services.ingest_job_service import IngestJobService
from app.tools.adapters import ProductionChunkSearcher
from tests.support.upload_harness import (
    DIMENSION,
    client_for,
    make_page,
    make_parser_patch,
    poll_until_terminal,
    upload,
    upload_env as build_upload_env,
)

pytestmark = [pytest.mark.integration]


@pytest.fixture
def upload_env(tmp_path):
    """本文件用独立库名，方便失败时按用例定位（其余共用件见 tests/support/upload_harness.py）。"""
    with build_upload_env(tmp_path, database_name="workspace.sqlite3") as harness:
        yield harness


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
