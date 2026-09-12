"""
trace_id 的上下文传播。

为什么用 contextvars 而不是层层传参：`trace_id` 会被 provider 包装、检索、摄取等多个
互不认识的层次用到，逐层加参数会污染一堆签名。`asyncio.to_thread` 与线程池都会复制当前
context，所以丢进线程池的同步代码里也能拿到同一个 ID。

见 docs/specs/us-stage1-trace.md §3.3。
"""
from contextvars import ContextVar, Token
from uuid import uuid4

_trace_id: ContextVar[str | None] = ContextVar("greenbean_trace_id", default=None)


def new_trace_id() -> str:
    """生成一个新的 trace ID。"""
    return str(uuid4())


def current_trace_id() -> str | None:
    """当前上下文里的 trace ID；没有绑定时返回 None。"""
    return _trace_id.get()


def bind_trace(trace_id: str | None = None) -> Token:
    """绑定 trace ID（不传或传 None 则新生成一个），返回可用于 `reset_trace` 的 token。"""
    return _trace_id.set(trace_id or new_trace_id())


def reset_trace(token: Token) -> None:
    """恢复到绑定之前的状态（必须在生成 token 的同一上下文里调用）。"""
    _trace_id.reset(token)
