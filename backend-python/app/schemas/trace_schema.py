"""trace 查询接口的响应 Schema。"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.entities import AgentTrace
from app.enums import TraceStatus


class TraceSpanPayload(BaseModel):
    """一条 span 在 HTTP 上的投影。"""

    span_name: str = Field(..., description="span 名称。")
    status: TraceStatus = Field(..., description="span 结局。")
    duration_ms: float = Field(..., description="耗时（毫秒）。")
    attributes: dict[str, Any] = Field(default_factory=dict, description="结构化属性。")
    error: str | None = Field(default=None, description="失败原因。")
    parent_id: str | None = Field(default=None, description="父 span ID。")
    created_at: datetime = Field(..., description="记录时间。")

    @classmethod
    def from_span(cls, span: AgentTrace) -> "TraceSpanPayload":
        return cls(
            span_name=span.span_name,
            status=span.status,
            duration_ms=span.duration_ms,
            attributes=span.attributes,
            error=span.error,
            parent_id=span.parent_id,
            created_at=span.created_at,
        )


class TracePayload(BaseModel):
    """一条 trace 的全貌：定序好的 span 列表。"""

    trace_id: str = Field(..., description="追踪 ID。")
    spans: list[TraceSpanPayload] = Field(default_factory=list, description="按发生顺序排列。")

    @classmethod
    def from_spans(cls, trace_id: str, spans: list[AgentTrace]) -> "TracePayload":
        return cls(
            trace_id=trace_id,
            spans=[TraceSpanPayload.from_span(span) for span in spans],
        )
