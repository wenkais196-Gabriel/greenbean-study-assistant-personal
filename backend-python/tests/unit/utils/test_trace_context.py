"""trace_id 的上下文传播（app/utils/trace_context）。"""
from app.utils.trace_context import bind_trace, current_trace_id, new_trace_id, reset_trace


def test_new_trace_id_is_unique():
    assert new_trace_id() != new_trace_id()


def test_unbound_context_has_no_trace_id():
    assert current_trace_id() is None


def test_bind_without_argument_generates_an_id():
    token = bind_trace()

    assert current_trace_id()

    reset_trace(token)


def test_bind_explicit_id_and_reset_restores_previous_state():
    token = bind_trace("trace-1")

    assert current_trace_id() == "trace-1"

    reset_trace(token)

    assert current_trace_id() is None


def test_nested_bind_keeps_the_outer_id_after_reset():
    outer = bind_trace("outer")
    inner = bind_trace("inner")

    assert current_trace_id() == "inner"

    reset_trace(inner)

    assert current_trace_id() == "outer"

    reset_trace(outer)


def test_bind_with_none_generates_a_fresh_id():
    """链路上游没有 trace 时（例如直接调 service），自己生成一个而不是留空。"""
    token = bind_trace(None)

    assert current_trace_id()

    reset_trace(token)
