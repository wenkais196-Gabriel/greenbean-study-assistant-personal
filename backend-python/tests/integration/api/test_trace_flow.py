"""
问答链路的 trace 端到端：一次提问落 4 条 span，且 trace_id 能从响应带回来。

用真 sqlite-vec + 假嵌入 + 假 provider（CI 不下载模型、不调外部 API）。
对应规格：docs/specs/us-stage1-trace.md（AC2 / AC3 / AC4 / AC7）
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.chat_controller import get_chat_service
from app.db.init_db import initialize_database, load_sqlite_vec_extension
from app.db.orm import create_database_engine, create_session_factory
from app.main import app
from app.providers.base import ChatResult
from app.services.chat_service import ChatService
from app.services.document_ingest_service import DocumentIngestService
from app.services.embedding_service import EmbeddingService
from app.services.trace_recorder import TraceRecorder

pytestmark = [pytest.mark.integration]

DIMENSION = 8
MODEL_NAME = "fake-embedding-model"
ROUTE_JSON = '{"route": "CONCEPT", "reason": "concept question"}'

# span 是"操作结束时"落库的，所以路由那次 gen_ai.chat 排在 agent.route **之前**
# （route 值要等 LLM 返回才知道）
EXPECTED_SPANS = [
    "gen_ai.chat",
    "agent.route",
    "retrieval.search",
    "context.build",
    "gen_ai.chat",
]


class FakeEmbeddingModel:
    def embed(self, texts, batch_size=None):
        for index, _ in enumerate(list(texts)):
            yield [float(index) + 1.0] * DIMENSION


@pytest.fixture
def trace_env(tmp_path, text_two_pages_pdf_bytes):
    initialization = initialize_database(
        data_dir=tmp_path / "data",
        database_name="trace.sqlite3",
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
    recorder = TraceRecorder(session_factory=session_factory)
    service = ChatService(
        session_factory=session_factory,
        embedding_service=embedding_service,
        embedding_dimension=DIMENSION,
        top_k=3,
        trace_recorder=recorder,
    )
    DocumentIngestService(
        session_factory=session_factory,
        embedding_service=embedding_service,
        embedding_model=MODEL_NAME,
        embedding_dimension=DIMENSION,
    ).ingest_document("text_two_pages.pdf", text_two_pages_pdf_bytes, workspace_id="ws-1")
    try:
        yield service, recorder
    finally:
        engine.dispose()


def ask(service, recorder):
    """发一次提问（假 provider），返回 (响应体, 该 trace 的 span 列表)。"""
    app.dependency_overrides[get_chat_service] = lambda: service
    try:
        with patch("app.agents.classification_agent.ProviderRegistry") as router_patch, patch(
            "app.agents.chat_agent.ProviderRegistry"
        ) as chat_patch:
            router_provider = MagicMock()
            router_provider.chat_completion = AsyncMock(
                return_value=ChatResult(content=ROUTE_JSON, input_tokens=42, output_tokens=8)
            )
            router_patch.get_active.return_value = router_provider

            chat_provider = MagicMock()
            chat_provider.chat_completion = AsyncMock(
                return_value=ChatResult(
                    content="Le cours présente ... [来源 1]",
                    input_tokens=1500,
                    output_tokens=120,
                    model="fake-model-0613",
                    finish_reason="stop",
                )
            )
            chat_patch.get_active.return_value = chat_provider

            response = TestClient(app).post(
                "/api/chat",
                json={"session_id": "s1", "query": "这份文档讲了什么？"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    trace_id = response.json()["trace_id"]
    return response.json(), recorder.get_trace(trace_id)


def test_one_question_produces_a_structured_trace(trace_env):
    service, recorder = trace_env

    body, spans = ask(service, recorder)

    assert body["answer"]
    assert body["trace_id"], "trace_id 必须能从响应带回来（AC2）"
    assert [span.span_name for span in spans] == EXPECTED_SPANS
    assert all(span.trace_id == body["trace_id"] for span in spans)


def test_route_span_records_the_decision(trace_env):
    service, recorder = trace_env

    _, spans = ask(service, recorder)

    route_span = next(span for span in spans if span.span_name == "agent.route")
    assert route_span.attributes["greenbean.route"] == "CONCEPT"
    assert route_span.attributes["greenbean.route.degraded"] is False


def test_retrieval_and_context_spans_record_scale(trace_env):
    service, recorder = trace_env

    _, spans = ask(service, recorder)

    retrieval = next(span for span in spans if span.span_name == "retrieval.search")
    assert retrieval.attributes["greenbean.retrieval.top_k"] == 3
    assert retrieval.attributes["greenbean.retrieval.hits"] > 0

    context = next(span for span in spans if span.span_name == "context.build")
    assert context.attributes["greenbean.context.items"] > 0
    assert context.attributes["greenbean.context.chars"] > 0


def test_llm_span_records_gen_ai_fields(trace_env):
    service, recorder = trace_env

    _, spans = ask(service, recorder)

    chat_spans = [span for span in spans if span.span_name == "gen_ai.chat"]
    assert len(chat_spans) == 2, "路由与回答各一次 LLM 调用"
    purposes = {span.attributes["greenbean.purpose"] for span in chat_spans}
    assert purposes == {"router", "answer"}

    answer_span = next(
        span for span in chat_spans if span.attributes["greenbean.purpose"] == "answer"
    )
    assert answer_span.attributes["gen_ai.operation.name"] == "chat"
    assert answer_span.attributes["gen_ai.usage.input_tokens"] == 1500
    assert answer_span.attributes["gen_ai.usage.output_tokens"] == 120
    assert answer_span.attributes["gen_ai.response.model"] == "fake-model-0613"
    assert answer_span.attributes["gen_ai.response.finish_reasons"] == ["stop"]
    assert answer_span.duration_ms >= 0
