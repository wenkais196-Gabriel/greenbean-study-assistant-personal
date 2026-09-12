"""
结构化 trace 的记录器：把一次操作落成一条 span。

**两条硬约束**（见 docs/specs/us-stage1-trace.md §3.4）：

1. **不接收 session，自己开会话** —— 这样"在数据库事务内误用"会立刻炸成
   `database is locked`，而不是留下难以察觉的部分提交（SQLite 只允许一个写者，
   教训见 us-stage1-upload-async.md §3.2）。所以**摄取路径的 span 一律在事务之外写**。
2. **关闭时是空操作**：`TRACE_ENABLED=False` 时 `record_span` 直接返回 `None`，
   一次数据库都不碰，链路行为与从前完全一致。
"""
import time
from contextlib import contextmanager
from functools import lru_cache
from typing import Any, Iterator

from app.config.settings import TRACE_ENABLED
from app.db.orm import SessionFactory
from app.entities import AgentTrace
from app.enums import TraceStatus
from app.repositories.agent_trace_repository import AgentTraceRepository
from app.utils.trace_context import current_trace_id, new_trace_id


def elapsed_ms(started: float) -> float:
    """从 `time.perf_counter()` 的起点算到现在的毫秒数（保留 3 位小数）。"""
    return round((time.perf_counter() - started) * 1000, 3)


class TraceRecorder:
    def __init__(
        self,
        *,
        session_factory: SessionFactory,
        enabled: bool = TRACE_ENABLED,
    ) -> None:
        self.session_factory = session_factory
        self.enabled = enabled

    def record_span(
        self,
        *,
        span_name: str,
        duration_ms: float,
        attributes: dict[str, Any] | None = None,
        status: TraceStatus = TraceStatus.OK,
        error: str | None = None,
        parent_id: str | None = None,
        trace_id: str | None = None,
    ) -> AgentTrace | None:
        """写入一条 span；关闭时返回 `None`。

        `attributes` 里的 `None` 值会被丢掉 —— semconv 的惯例是缺失字段省略，
        留一堆 null 会让后续聚合多写一堆判空。
        """
        if not self.enabled:
            return None

        span = AgentTrace(
            trace_id=trace_id or self._resolve_trace_id(),
            parent_id=parent_id,
            span_name=span_name,
            status=status,
            duration_ms=duration_ms,
            attributes={
                key: value for key, value in (attributes or {}).items() if value is not None
            },
            error=error,
        )
        with self.session_factory() as session:
            AgentTraceRepository(session).save(span)
            session.commit()
        return span

    @contextmanager
    def span(self, span_name: str, **attributes: Any) -> Iterator[None]:
        """包住一段代码：自动计时，退出时落一条 span；异常**照原样重抛**。

        属性必须在进入时就已知（比如阶段名）。需要"结束时才知道"的属性
        （页数、片段数）请直接用 `record_span`。
        """
        started = time.perf_counter()
        try:
            yield
        except Exception as exc:
            self.record_span(
                span_name=span_name,
                duration_ms=elapsed_ms(started),
                attributes=attributes,
                status=TraceStatus.ERROR,
                error=f"{type(exc).__name__}: {exc}",
            )
            raise
        self.record_span(
            span_name=span_name,
            duration_ms=elapsed_ms(started),
            attributes=attributes,
        )

    def get_trace(self, trace_id: str) -> list[AgentTrace]:
        """取回一条 trace 的全部 span（按发生顺序）；关闭时返回空列表。"""
        if not self.enabled:
            return []
        with self.session_factory() as session:
            return AgentTraceRepository(session).list_by_trace(trace_id)

    @staticmethod
    def _resolve_trace_id() -> str:
        """优先用上下文里的 ID；没有就临时生成一个。

        **不写回上下文**：绑定了却不重置，会把 ID 泄漏给同一线程后续的调用
        （在测试进程里尤其明显）。真正需要"一次链路共享一个 ID"的调用方
        （`ChatService` / `DocumentIngestService`）已经自己 bind / reset 了。
        """
        return current_trace_id() or new_trace_id()


@lru_cache(maxsize=1)
def production_trace_recorder() -> TraceRecorder | None:
    """生产用的 recorder（进程内单例）；`TRACE_ENABLED=False` 时返回 `None`。

    关闭时返回 None 而不是一个 disabled 实例：调用方拿到的就是"没有 recorder"，
    走无 trace 路径，不需要知道开关的存在（见 docs/specs/us-stage1-trace.md AC9）。
    会话工厂懒加载 —— 构造它不会建库。
    """
    if not TRACE_ENABLED:
        return None

    from app.db.runtime import lazy_session_factory

    return TraceRecorder(session_factory=lazy_session_factory())
