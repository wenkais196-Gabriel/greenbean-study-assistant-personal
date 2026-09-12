"""
TraceRecorder 单元测试：span 写入、失败留痕、采样开关与 trace_id 归属。

用真 SQLite（`Base.metadata.create_all`，不需要 sqlite-vec）验证落库与 JSON 往返。

对应规格：docs/specs/us-stage1-trace.md（AC1 / AC6 / AC7 / AC9）
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base
from app.enums import TraceStatus
from app.services.trace_recorder import TraceRecorder
from app.utils.trace_context import bind_trace, reset_trace

FIXED_TRACE_ID = "test-trace"


@pytest.fixture
def session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'trace.sqlite3').as_posix()}")
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
    """绑定固定 trace_id 供读回断言 —— 不依赖 recorder 里的隐藏状态。"""
    token = bind_trace(FIXED_TRACE_ID)
    try:
        yield FIXED_TRACE_ID
    finally:
        reset_trace(token)


# ========== 写入与读取 ==========


def test_span_records_duration_status_and_attributes(recorder, bound_trace):
    with recorder.span("retrieval.search", **{"greenbean.retrieval.top_k": 20}):
        pass

    spans = recorder.get_trace(bound_trace)
    assert len(spans) == 1
    span = spans[0]
    assert span.span_name == "retrieval.search"
    assert span.status is TraceStatus.OK
    assert span.duration_ms >= 0
    assert span.attributes["greenbean.retrieval.top_k"] == 20
    assert span.error is None


def test_span_returns_the_recorded_row(recorder):
    span = recorder.record_span(span_name="ingest.parsing", duration_ms=12.5)

    assert span is not None
    assert span.span_name == "ingest.parsing"
    assert span.duration_ms == 12.5


def test_get_trace_returns_spans_in_creation_order(recorder, bound_trace):
    recorder.record_span(span_name="first", duration_ms=1.0)
    recorder.record_span(span_name="second", duration_ms=2.0)
    recorder.record_span(span_name="third", duration_ms=3.0)

    assert [span.span_name for span in recorder.get_trace(bound_trace)] == [
        "first",
        "second",
        "third",
    ]


def test_get_trace_returns_empty_for_unknown_id(recorder):
    assert recorder.get_trace("does-not-exist") == []


def test_attributes_survive_json_round_trip(recorder, bound_trace):
    """属性里可能有嵌套结构与中文（route 原因、错误文案），必须原样存回来。"""
    recorder.record_span(
        span_name="gen_ai.chat",
        duration_ms=1.0,
        attributes={"nested": {"a": [1, 2]}, "zh": "路由降级", "none": None},
    )

    attributes = recorder.get_trace(bound_trace)[0].attributes
    assert attributes["nested"] == {"a": [1, 2]}
    assert attributes["zh"] == "路由降级"


# ========== trace_id 归属 ==========


def test_record_span_uses_the_bound_trace_id(recorder, bound_trace):
    span = recorder.record_span(span_name="x", duration_ms=1.0)

    assert span.trace_id == bound_trace


def test_record_span_generates_an_id_when_nothing_is_bound(recorder):
    """链路上游没有 trace 时（例如直接调 service）自己生成一个，而不是留空。"""
    span = recorder.record_span(span_name="x", duration_ms=1.0)

    assert span.trace_id


def test_record_span_accepts_an_explicit_trace_id(recorder):
    span = recorder.record_span(span_name="x", duration_ms=1.0, trace_id="explicit")

    assert span.trace_id == "explicit"


def test_parent_id_is_persisted(recorder, bound_trace):
    parent = recorder.record_span(span_name="parent", duration_ms=1.0)

    child = recorder.record_span(span_name="child", duration_ms=1.0, parent_id=parent.id)

    assert child.parent_id == parent.id
    assert [span.span_name for span in recorder.get_trace(bound_trace)] == ["parent", "child"]


# ========== 失败路径：留痕但不改变行为（AC6） ==========


def test_failed_span_is_recorded_and_the_exception_is_reraised(recorder, bound_trace):
    with pytest.raises(ValueError, match="解析失败"):
        with recorder.span("ingest.parsing"):
            raise ValueError("解析失败")

    spans = recorder.get_trace(bound_trace)
    assert len(spans) == 1
    assert spans[0].status is TraceStatus.ERROR
    assert spans[0].error is not None and "解析失败" in spans[0].error


def test_record_span_accepts_an_explicit_error(recorder):
    span = recorder.record_span(
        span_name="gen_ai.chat",
        duration_ms=1.0,
        status=TraceStatus.ERROR,
        error="TimeoutError: 超时",
    )

    assert span.status is TraceStatus.ERROR
    assert span.error == "TimeoutError: 超时"


# ========== 采样开关（AC9） ==========


def test_disabled_recorder_writes_nothing(session_factory, bound_trace):
    recorder = TraceRecorder(session_factory=session_factory, enabled=False)

    assert recorder.record_span(span_name="x", duration_ms=1.0) is None

    with recorder.span("y"):
        pass

    assert recorder.get_trace(bound_trace) == []


def test_disabled_span_still_reraises_exceptions(session_factory):
    """关掉 trace 不等于吃掉异常：被观测的代码该报错还得报错。"""
    recorder = TraceRecorder(session_factory=session_factory, enabled=False)

    with pytest.raises(RuntimeError, match="boom"):
        with recorder.span("x"):
            raise RuntimeError("boom")
