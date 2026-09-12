from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field

from app.enums.ingest_job_status import IngestJobStatus
from app.enums.ingest_stage import IngestStage


class IngestJob(BaseModel):
    """一次上传摄取任务的进度载体（持久化在 `ingest_jobs` 表）。

    上传改成异步后，"这次上传到哪一步了"必须能在**请求之外**、且**进程重启之后**被查到，
    所以它是实体而不是进程内字典（取舍见 docs/specs/us-stage1-upload-async.md §3.1）。
    """

    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="任务唯一 ID，使用 UUID 字符串。",
    )
    filename: str = Field(..., description="用户上传时的原始文件名。")
    workspace_id: str = Field(default="", description="所属工作区 ID。")
    status: IngestJobStatus = Field(
        default=IngestJobStatus.QUEUED, description="任务状态。"
    )
    stage: IngestStage | None = Field(
        default=None, description="当前阶段；尚未开始或已结束时为 None。"
    )
    progress: float = Field(default=0.0, description="整体进度，取值 0~1，且单调不减。")
    error: str | None = Field(default=None, description="失败原因，成功时为 None。")
    result: dict | None = Field(
        default=None,
        description="成功后的摄取摘要（可 JSON 序列化：实体换成 document_id 与计数）。",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="创建时间。"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="最后更新时间。"
    )
