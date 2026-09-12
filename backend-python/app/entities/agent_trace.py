from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from app.enums.trace_status import TraceStatus


class AgentTrace(BaseModel):
    """一条 span —— 一次可观测操作的完整记录。

    字段名对齐 OTel GenAI semconv 的 `gen_ai.*`（`attributes` 里），
    本项目特有的信息用 `greenbean.*` 前缀，互不污染。

    `parent_id` 本批**不建立**显式的父子层次（摄取与问答的 span 都是平铺的），
    留待阶段 3 做 trace 面板时再补真实层级。
    """

    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="span 唯一 ID，使用 UUID 字符串。",
    )
    trace_id: str = Field(..., description="所属追踪 ID；一次提问或一次上传共享一个。")
    parent_id: str | None = Field(default=None, description="父 span ID（本批保留不用）。")
    span_name: str = Field(..., description="span 名称，如 gen_ai.chat / ingest.parsing。")
    status: TraceStatus = Field(default=TraceStatus.OK, description="span 结局。")
    duration_ms: float = Field(..., description="耗时（毫秒）。")
    attributes: dict[str, Any] = Field(
        default_factory=dict, description="结构化属性（gen_ai.* / greenbean.*）。"
    )
    error: str | None = Field(default=None, description="失败原因；成功时为 None。")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="记录时间。"
    )
