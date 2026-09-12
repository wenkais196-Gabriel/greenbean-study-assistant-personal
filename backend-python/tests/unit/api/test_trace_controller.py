"""`GET /api/traces/{trace_id}`：trace 的读出口（AC8）。"""
import pytest
from fastapi.testclient import TestClient

from app.api.trace_controller import get_trace_recorder
from app.entities import AgentTrace
from app.enums import TraceStatus
from app.main import app
from app.services import trace_recorder as trace_recorder_module
from app.services.trace_recorder import TraceRecorder, production_trace_recorder


@pytest.fixture(autouse=True)
def clean_singleton():
    """`production_trace_recorder` 是进程内单例：测试之间必须清掉，否则会串开关状态。"""
    production_trace_recorder.cache_clear()
    yield
    production_trace_recorder.cache_clear()


@pytest.fixture
def client():
    return TestClient(app)


def make_span(**overrides) -> AgentTrace:
    data = {
        "trace_id": "trace-1",
        "span_name": "gen_ai.chat",
        "status": TraceStatus.OK,
        "duration_ms": 123.4,
        "attributes": {"gen_ai.usage.input_tokens": 120},
    }
    data.update(overrides)
    return AgentTrace(**data)


def override_recorder(recorder) -> None:
    """注入假 recorder。

    ⚠️ 必须走 `dependency_overrides`：`Depends(get_trace_recorder)` 在定义时就捕获了
    那个函数对象，`monkeypatch.setattr` 改模块属性对它无效。
    """
    app.dependency_overrides[get_trace_recorder] = lambda: recorder


def test_get_trace_recorder_wraps_the_production_singleton():
    recorder = get_trace_recorder()

    assert isinstance(recorder, TraceRecorder)
    assert get_trace_recorder() is recorder


def test_get_trace_recorder_returns_none_when_tracing_is_disabled(monkeypatch):
    """关闭 trace 时依赖注入直接给 None —— 调用方走无 trace 路径（AC9）。"""
    monkeypatch.setattr(trace_recorder_module, "TRACE_ENABLED", False)

    assert get_trace_recorder() is None


def test_returns_spans_of_the_trace(client):
    recorder = TraceRecorder(session_factory=lambda: None)  # 读路径用假实现，不碰数据库
    recorder.get_trace = lambda trace_id: [make_span(), make_span(span_name="agent.route")]
    override_recorder(recorder)
    try:
        response = client.get("/api/traces/trace-1")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["trace_id"] == "trace-1"
    assert [span["span_name"] for span in payload["spans"]] == ["gen_ai.chat", "agent.route"]
    assert payload["spans"][0]["attributes"]["gen_ai.usage.input_tokens"] == 120
    assert payload["spans"][0]["status"] == "ok"


def test_unknown_trace_returns_404(client):
    recorder = TraceRecorder(session_factory=lambda: None)
    recorder.get_trace = lambda trace_id: []
    override_recorder(recorder)
    try:
        response = client.get("/api/traces/nope")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert "nope" in response.json()["detail"]


def test_disabled_tracing_returns_404(client):
    """trace 关掉时没有数据可查 —— 明确 404，而不是 500。"""
    override_recorder(None)
    try:
        response = client.get("/api/traces/trace-1")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
