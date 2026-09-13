"""
聊天链路端到端：上传 → 提问 → 带来源的回答。

用真 sqlite-vec + 假嵌入模型 + 假 provider（CI 既不下载模型、也不调用外部 API）。
这里验证的正是"开口"要保证的东西：`POST /api/chat` 真的把检索到的资料喂给了模型，
并把来源原样带回来供引用回溯。
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.chat_controller import get_chat_service
from app.db.init_db import initialize_database, load_sqlite_vec_extension
from app.db.orm import create_database_engine, create_session_factory
from app.enums.route_types import RouteType
from app.main import app
from app.providers.base import ChatResult
from app.providers.registry import ProviderNotFoundError
from app.services.chat_service import ChatService
from app.services.document_ingest_service import DocumentIngestService
from app.services.embedding_service import EmbeddingService

pytestmark = [pytest.mark.integration]

DIMENSION = 8
MODEL_NAME = "fake-embedding-model"
ROUTE_JSON = '{"route": "CONCEPT", "reason": "concept question"}'
ANSWER_WITH_CITATION = "Le cours présente ... [来源 1]"


class FakeEmbeddingModel:
    """按批内顺序返回确定向量：query 落在 index 0，必然命中最先入库的片段。"""

    def embed(self, texts, batch_size=None):
        for index, _ in enumerate(list(texts)):
            yield [float(index) + 1.0] * DIMENSION


@pytest.fixture
def chat_env(tmp_path, text_two_pages_pdf_bytes):
    result = initialize_database(
        data_dir=tmp_path / "data",
        database_name="chat.sqlite3",
        embedding_dimension=DIMENSION,
        sqlite_vec_loader=load_sqlite_vec_extension,
    )
    engine = create_database_engine(
        result.database_path,
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
    service = ChatService(
        session_factory=session_factory,
        embedding_service=embedding_service,
        embedding_dimension=DIMENSION,
        top_k=3,
    )
    try:
        yield service, session_factory, embedding_service, text_two_pages_pdf_bytes
    finally:
        engine.dispose()


def _ingest(session_factory, embedding_service, pdf_bytes) -> None:
    DocumentIngestService(
        session_factory=session_factory,
        embedding_service=embedding_service,
        embedding_model=MODEL_NAME,
        embedding_dimension=DIMENSION,
    ).ingest_document("text_two_pages.pdf", pdf_bytes, workspace_id="ws-1")


def _patched_providers():
    """把路由与回答两个 Registry 都换成假 provider（返回上下文管理器）。"""
    return (
        patch("app.agents.classification_agent.ProviderRegistry"),
        patch("app.agents.chat_agent.ProviderRegistry"),
    )


def test_chat_endpoint_returns_answer_with_retrieval_sources(chat_env):
    service, session_factory, embedding_service, pdf_bytes = chat_env
    _ingest(session_factory, embedding_service, pdf_bytes)

    router_registry, chat_registry = _patched_providers()
    app.dependency_overrides[get_chat_service] = lambda: service
    try:
        with router_registry as router_patch, chat_registry as chat_patch:
            router_provider = MagicMock()
            router_provider.chat_completion = AsyncMock(
                return_value=ChatResult(content=ROUTE_JSON)
            )
            router_patch.get_active.return_value = router_provider

            chat_provider = MagicMock()
            chat_provider.chat_completion = AsyncMock(
                return_value=ChatResult(content=ANSWER_WITH_CITATION)
            )
            chat_patch.get_active.return_value = chat_provider

            response = TestClient(app).post(
                "/api/chat",
                json={"session_id": "s1", "query": "这份文档讲了什么？"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == "s1"
    assert body["answer"] == ANSWER_WITH_CITATION

    # 来源必须带回来（引用回溯的原料）
    assert body["source_context"], "回答必须带上检索来源"
    first = body["source_context"][0]
    assert first["chunk_id"]
    assert first["page_number"] in (1, 2)

    # 上下文确实被拼进了发给模型的 prompt
    prompt = chat_provider.chat_completion.call_args.kwargs["messages"][-1]["content"]
    assert "### Course Context" in prompt
    assert "[来源 1]" in prompt
    assert "这份文档讲了什么？" in prompt


def test_chat_with_empty_index_still_answers(chat_env):
    """资料还没上传时不能炸：上下文与来源为空，但仍返回回答。"""
    service, *_ = chat_env

    router_registry, chat_registry = _patched_providers()
    app.dependency_overrides[get_chat_service] = lambda: service
    try:
        with router_registry as router_patch, chat_registry as chat_patch:
            router_provider = MagicMock()
            router_provider.chat_completion = AsyncMock(
                return_value=ChatResult(content=ROUTE_JSON)
            )
            router_patch.get_active.return_value = router_provider

            chat_provider = MagicMock()
            chat_provider.chat_completion = AsyncMock(
                return_value=ChatResult(content="我没有找到相关资料。")
            )
            chat_patch.get_active.return_value = chat_provider

            response = TestClient(app).post(
                "/api/chat",
                json={"session_id": "s2", "query": "随便问问"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["source_context"] == []


def test_chat_returns_503_when_no_provider_is_activated(chat_env):
    """provider 没配置时给出 503 + 可读提示，而不是 500 堆栈。"""
    service, *_ = chat_env
    app.dependency_overrides[get_chat_service] = lambda: service
    try:
        with patch("app.agents.classification_agent.ProviderRegistry") as router_patch:
            router_patch.get_active.side_effect = ProviderNotFoundError("没有激活的 provider")
            response = TestClient(app).post(
                "/api/chat",
                json={"session_id": "s3", "query": "问题"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert "provider" in response.json()["detail"]


def test_chat_rejects_blank_query(chat_env):
    service, *_ = chat_env
    app.dependency_overrides[get_chat_service] = lambda: service
    try:
        response = TestClient(app).post(
            "/api/chat",
            json={"session_id": "s4", "query": "   "},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400


def test_retrieval_depth_follows_route_and_extended_flag(chat_env):
    """路由决策真的影响行为：综合类问题拿双倍候选，"扩展上下文"同样翻倍。"""
    service, *_ = chat_env

    assert service._retrieval_depth(RouteType.CONCEPT, False) == service.top_k
    assert service._retrieval_depth(RouteType.STRUCTURE, False) == service.top_k
    assert service._retrieval_depth(RouteType.COMPREHENSIVE, False) == service.top_k * 2
    assert service._retrieval_depth(RouteType.CONCEPT, True) == service.top_k * 2


def test_get_chat_service_returns_a_configured_service_without_touching_disk():
    """依赖注入函数本身也要可用：构造 service 时**不建库**（会话工厂是懒的）。"""
    service = get_chat_service()

    assert isinstance(service, ChatService)
    assert callable(service.session_factory)


def test_chat_response_carries_token_usage(chat_env):
    """回答的 token 用量要回传（前端 TokenUsage 与成本账本的原料）。

    口径：只报**回答**那次 LLM 调用的用量；路由那次是内部决策开销，不计入。
    """
    service, session_factory, embedding_service, pdf_bytes = chat_env
    _ingest(session_factory, embedding_service, pdf_bytes)

    router_registry, chat_registry = _patched_providers()
    app.dependency_overrides[get_chat_service] = lambda: service
    try:
        with router_registry as router_patch, chat_registry as chat_patch:
            router_provider = MagicMock()
            router_provider.chat_completion = AsyncMock(
                return_value=ChatResult(content=ROUTE_JSON, input_tokens=80, output_tokens=12)
            )
            router_patch.get_active.return_value = router_provider

            chat_provider = MagicMock()
            chat_provider.chat_completion = AsyncMock(
                return_value=ChatResult(
                    content=ANSWER_WITH_CITATION,
                    input_tokens=1500,
                    output_tokens=210,
                )
            )
            chat_patch.get_active.return_value = chat_provider

            response = TestClient(app).post(
                "/api/chat",
                json={"session_id": "s-usage", "query": "这份文档讲了什么？"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    usage = response.json()["usage"]
    assert usage["input_tokens"] == 1500
    assert usage["output_tokens"] == 210


def test_chat_usage_is_null_when_provider_omits_it(chat_env):
    """provider 不回传用量时是 None（兼容端点不保证给），而不是编一个数。"""
    service, *_ = chat_env

    router_registry, chat_registry = _patched_providers()
    app.dependency_overrides[get_chat_service] = lambda: service
    try:
        with router_registry as router_patch, chat_registry as chat_patch:
            router_provider = MagicMock()
            router_provider.chat_completion = AsyncMock(
                return_value=ChatResult(content=ROUTE_JSON)
            )
            router_patch.get_active.return_value = router_provider

            chat_provider = MagicMock()
            chat_provider.chat_completion = AsyncMock(
                return_value=ChatResult(content="我没有找到相关资料。")
            )
            chat_patch.get_active.return_value = chat_provider

            response = TestClient(app).post(
                "/api/chat",
                json={"session_id": "s-nousage", "query": "随便问问"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["usage"] is None


# ===== 会话与消息持久化（收尾 ②）=====
# 本节的 import 就近放在这里，避免改动文件顶部的既有 import 区块。
from contextlib import contextmanager  # noqa: E402

from app.enums.message_role import MessageRole  # noqa: E402
from app.repositories.chat_message_repository import ChatMessageRepository  # noqa: E402
from app.repositories.chat_session_repository import ChatSessionRepository  # noqa: E402

DEFAULT_WORKSPACE_ID = "default"


@contextmanager
def _stub_providers(answer: str = ANSWER_WITH_CITATION):
    """把路由与回答两个 Registry 都换成假 provider；产出回答那次 provider 供断言。"""
    router_registry, chat_registry = _patched_providers()
    with router_registry as router_patch, chat_registry as chat_patch:
        router_provider = MagicMock()
        router_provider.chat_completion = AsyncMock(return_value=ChatResult(content=ROUTE_JSON))
        router_patch.get_active.return_value = router_provider

        chat_provider = MagicMock()
        chat_provider.chat_completion = AsyncMock(return_value=ChatResult(content=answer))
        chat_patch.get_active.return_value = chat_provider
        yield chat_provider


def _ask(session_id: str, query: str, **extra):
    return TestClient(app).post(
        "/api/chat",
        json={"session_id": session_id, "query": query, **extra},
    )


def _stored_session(session_factory, session_id: str):
    with session_factory() as session:
        return ChatSessionRepository(session).get_by_id(session_id)


def _stored_messages(session_factory, session_id: str):
    with session_factory() as session:
        return ChatMessageRepository(session).list_by_session(session_id)


def test_question_persists_session_and_messages(chat_env):
    """一次提问落一条会话 + 两条消息，助手消息带来源（刷新后引用仍可回溯）。"""
    service, session_factory, embedding_service, pdf_bytes = chat_env
    _ingest(session_factory, embedding_service, pdf_bytes)

    app.dependency_overrides[get_chat_service] = lambda: service
    try:
        with _stub_providers():
            response = _ask("s-persist", "这份文档讲了什么？", workspace_id="ws-persist")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200

    stored = _stored_session(session_factory, "s-persist")
    assert stored is not None, "首次提问必须自动建会话"
    assert stored.workspace_id == "ws-persist"
    assert stored.title == "这份文档讲了什么？"

    messages = _stored_messages(session_factory, "s-persist")
    assert [m.role for m in messages] == [MessageRole.USER, MessageRole.AGENT]
    assert messages[0].content == "这份文档讲了什么？"
    assert messages[1].content == ANSWER_WITH_CITATION
    assert messages[1].source_context_json, "助手消息要带上来源"


def test_second_question_reuses_session_and_keeps_history(chat_env):
    """同一 session_id 复用既有会话：不重复建行，也不覆盖历史。"""
    service, session_factory, embedding_service, pdf_bytes = chat_env
    _ingest(session_factory, embedding_service, pdf_bytes)

    app.dependency_overrides[get_chat_service] = lambda: service
    try:
        with _stub_providers():
            first = _ask("s-reuse", "第一问")
            second = _ask("s-reuse", "第二问")
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 200
    assert second.status_code == 200

    stored = _stored_session(session_factory, "s-reuse")
    assert stored is not None
    assert stored.title == "第一问", "标题取首问，不随后续问题改"

    messages = _stored_messages(session_factory, "s-reuse")
    assert [m.content for m in messages] == [
        "第一问",
        ANSWER_WITH_CITATION,
        "第二问",
        ANSWER_WITH_CITATION,
    ]


def test_workspace_id_defaults_when_request_omits_it(chat_env):
    """请求不带 workspace_id 时归到默认工作区（前端也用它）。"""
    service, session_factory, embedding_service, pdf_bytes = chat_env
    _ingest(session_factory, embedding_service, pdf_bytes)

    app.dependency_overrides[get_chat_service] = lambda: service
    try:
        with _stub_providers():
            response = _ask("s-default", "问题")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert _stored_session(session_factory, "s-default").workspace_id == DEFAULT_WORKSPACE_ID


def test_session_messages_endpoint_returns_history(chat_env):
    """GET /api/chat/sessions/{id}/messages 回读历史，按时间升序。"""
    service, session_factory, embedding_service, pdf_bytes = chat_env
    _ingest(session_factory, embedding_service, pdf_bytes)

    app.dependency_overrides[get_chat_service] = lambda: service
    try:
        with _stub_providers():
            _ask("s-history", "第一问")
            _ask("s-history", "第二问")
        response = TestClient(app).get("/api/chat/sessions/s-history/messages")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert [item["role"] for item in body] == ["user", "agent", "user", "agent"]
    assert [item["content"] for item in body] == [
        "第一问",
        ANSWER_WITH_CITATION,
        "第二问",
        ANSWER_WITH_CITATION,
    ]
    assert body[1]["source_context_json"], "历史里的助手消息也要带来源"


def test_session_messages_endpoint_returns_404_for_unknown_session(chat_env):
    service, *_ = chat_env
    app.dependency_overrides[get_chat_service] = lambda: service
    try:
        response = TestClient(app).get("/api/chat/sessions/does-not-exist/messages")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


def test_failed_answer_does_not_persist(chat_env):
    """provider 没配好时提问失败，不该在历史里留下半截会话。"""
    service, session_factory, *_ = chat_env
    app.dependency_overrides[get_chat_service] = lambda: service
    try:
        with patch("app.agents.classification_agent.ProviderRegistry") as router_patch:
            router_patch.get_active.side_effect = ProviderNotFoundError("没有激活的 provider")
            response = _ask("s-failed", "问题")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert _stored_session(session_factory, "s-failed") is None
    assert _stored_messages(session_factory, "s-failed") == []
