"""
LLM 调用的 trace：`gen_ai.*` 字段映射、失败留痕、无 recorder 时直通。

对应规格：docs/specs/us-stage1-trace.md（AC3 / AC6 / AC10）
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.entities.provider_config import ProviderConfig
from app.enums import ApiMode, TraceStatus
from app.providers.base import ChatResult
from app.services.llm_trace import traced_chat_completion
from app.services.trace_recorder import TraceRecorder
from app.utils.trace_context import bind_trace, reset_trace

FIXED_TRACE_ID = "llm-trace"


class FakeProvider:
    """只要 `chat_completion` 与可选的 `config` —— 与真实 provider 的最小共同面。"""

    def __init__(self, *, result=None, error=None, config=None) -> None:
        self.result = result
        self.error = error
        self.calls: list[tuple[list[dict], dict]] = []
        if config is not None:
            self.config = config

    async def chat_completion(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        if self.error is not None:
            raise self.error
        return self.result


def make_config(**overrides) -> ProviderConfig:
    data = {
        "name": "test-provider",
        "api_mode": ApiMode.OPENAI_COMPAT,
        "api_key": "sk-test",
        "api_host": "https://api.test.com",
        "model_id": "test-model",
        "display_name": "test",
    }
    data.update(overrides)
    return ProviderConfig(**data)


@pytest.fixture
def session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'llm-trace.sqlite3').as_posix()}")
    Base.metadata.create_all(engine)
    try:
        yield sessionmaker(bind=engine, expire_on_commit=False)
    finally:
        engine.dispose()


@pytest.fixture
def recorder(session_factory):
    return TraceRecorder(session_factory=session_factory)


@pytest.fixture
def bound_trace():
    token = bind_trace(FIXED_TRACE_ID)
    try:
        yield FIXED_TRACE_ID
    finally:
        reset_trace(token)


def only_span(recorder, trace_id):
    spans = recorder.get_trace(trace_id)
    assert len(spans) == 1
    return spans[0]


# ========== AC3：字段映射 ==========


@pytest.mark.asyncio
async def test_records_gen_ai_attributes_for_a_successful_call(recorder, bound_trace):
    provider = FakeProvider(
        config=make_config(),
        result=ChatResult(
            content="回答",
            input_tokens=120,
            output_tokens=30,
            model="test-model-0613",
            finish_reason="stop",
        ),
    )

    result = await traced_chat_completion(
        provider,
        messages=[{"role": "user", "content": "hi"}],
        recorder=recorder,
        purpose="answer",
        temperature=0.3,
    )

    assert result.content == "回答"
    span = only_span(recorder, bound_trace)
    assert span.span_name == "gen_ai.chat"
    assert span.status is TraceStatus.OK
    assert span.attributes["gen_ai.operation.name"] == "chat"
    assert span.attributes["gen_ai.system"] == ApiMode.OPENAI_COMPAT.value
    assert span.attributes["gen_ai.request.model"] == "test-model"
    assert span.attributes["gen_ai.request.temperature"] == 0.3
    assert span.attributes["gen_ai.usage.input_tokens"] == 120
    assert span.attributes["gen_ai.usage.output_tokens"] == 30
    assert span.attributes["gen_ai.response.model"] == "test-model-0613"
    assert span.attributes["gen_ai.response.finish_reasons"] == ["stop"]
    assert span.attributes["greenbean.purpose"] == "answer"
    assert provider.calls[0][1]["temperature"] == 0.3


@pytest.mark.asyncio
async def test_explicit_model_argument_wins_over_the_config(recorder, bound_trace):
    provider = FakeProvider(config=make_config(), result=ChatResult(content="x"))

    await traced_chat_completion(
        provider,
        messages=[],
        recorder=recorder,
        model="override-model",
    )

    span = only_span(recorder, bound_trace)
    assert span.attributes["gen_ai.request.model"] == "override-model"


@pytest.mark.asyncio
async def test_missing_usage_fields_are_omitted(recorder, bound_trace):
    """semconv 里缺失字段应省略，而不是留一堆 null 影响聚合。"""
    provider = FakeProvider(config=make_config(), result=ChatResult(content="x"))

    await traced_chat_completion(provider, messages=[], recorder=recorder)

    attributes = only_span(recorder, bound_trace).attributes
    assert "gen_ai.usage.input_tokens" not in attributes
    assert "gen_ai.response.model" not in attributes
    assert "gen_ai.response.finish_reasons" not in attributes


@pytest.mark.asyncio
async def test_provider_without_config_reports_unknown_system(recorder, bound_trace):
    provider = FakeProvider(result=ChatResult(content="x"))

    await traced_chat_completion(provider, messages=[], recorder=recorder)

    attributes = only_span(recorder, bound_trace).attributes
    assert attributes["gen_ai.system"] == "unknown"
    assert "gen_ai.request.model" not in attributes


@pytest.mark.asyncio
async def test_max_tokens_is_recorded_when_provided(recorder, bound_trace):
    provider = FakeProvider(config=make_config(), result=ChatResult(content="x"))

    await traced_chat_completion(provider, messages=[], recorder=recorder, max_tokens=256)

    attributes = only_span(recorder, bound_trace).attributes
    assert attributes["gen_ai.request.max_tokens"] == 256


# ========== AC6：失败留痕 ==========


@pytest.mark.asyncio
async def test_failure_is_recorded_and_reraised(recorder, bound_trace):
    provider = FakeProvider(config=make_config(), error=TimeoutError("上游超时"))

    with pytest.raises(TimeoutError, match="上游超时"):
        await traced_chat_completion(provider, messages=[], recorder=recorder)

    span = only_span(recorder, bound_trace)
    assert span.status is TraceStatus.ERROR
    assert span.error is not None and "上游超时" in span.error


# ========== 无 recorder 时直通 ==========


@pytest.mark.asyncio
async def test_without_recorder_the_call_still_works():
    provider = FakeProvider(config=make_config(), result=ChatResult(content="ok"))

    result = await traced_chat_completion(provider, messages=[], recorder=None)

    assert result.content == "ok"
    assert len(provider.calls) == 1
