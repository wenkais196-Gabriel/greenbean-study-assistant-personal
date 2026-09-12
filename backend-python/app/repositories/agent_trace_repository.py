from sqlalchemy.orm import Session

from app.db.models import AgentTraceModel
from app.entities import AgentTrace
from app.enums import TraceStatus
from app.repositories.sqlite_helpers import datetime_value, json_object, json_value


class AgentTraceRepository:
    """`agent_traces` 表的读写：结构化 trace 的落点（docs/specs/us-stage1-trace.md §4）。"""

    def __init__(self, session: Session) -> None:
        self.session = session

    def save(self, trace: AgentTrace) -> AgentTrace:
        model = self.session.get(AgentTraceModel, trace.id)
        if model is None:
            model = AgentTraceModel(id=trace.id, created_at=datetime_value(trace.created_at))
            self.session.add(model)
        model.trace_id = trace.trace_id
        model.parent_id = trace.parent_id
        model.span_name = trace.span_name
        model.status = trace.status.value
        model.duration_ms = trace.duration_ms
        model.attributes_json = json_value(trace.attributes)
        model.error = trace.error
        return trace

    def list_by_trace(self, trace_id: str) -> list[AgentTrace]:
        """按 trace 取回全部 span，按发生顺序排列（`created_at` 是微秒精度 ISO 串）。"""
        models = (
            self.session.query(AgentTraceModel)
            .filter(AgentTraceModel.trace_id == trace_id)
            .order_by(AgentTraceModel.created_at)
            .all()
        )
        return [
            AgentTrace(
                id=model.id,
                trace_id=model.trace_id,
                parent_id=model.parent_id,
                span_name=model.span_name,
                status=TraceStatus(model.status),
                duration_ms=model.duration_ms,
                attributes=json_object(model.attributes_json) or {},
                error=model.error,
                created_at=model.created_at,
            )
            for model in models
        ]
