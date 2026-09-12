"""上传接口的 Schema：上传受理与进度查询共用同一个任务投影。"""
from datetime import datetime

from pydantic import BaseModel, Field

from app.entities import IngestJob
from app.enums.ingest_job_status import IngestJobStatus
from app.enums.ingest_stage import IngestStage


class IngestJobPayload(BaseModel):
    """上传任务在 HTTP 上的投影。

    `POST /api/documents/upload`（受理）与 `GET /api/documents/jobs/{job_id}`（轮询）
    返回**同一个形状**，前端因此只用一套解析逻辑。
    字段名用 `job_id` 而不是实体里的 `id`：它在 URL 里出现，叫得明确一点。
    """

    job_id: str = Field(..., description="任务 ID，用于轮询进度。")
    filename: str = Field(..., description="用户上传时的原始文件名。")
    status: IngestJobStatus = Field(..., description="任务状态。")
    stage: IngestStage | None = Field(
        default=None, description="当前阶段；未开始或已结束为 None。"
    )
    progress: float = Field(default=0.0, description="整体进度 0~1。")
    error: str | None = Field(default=None, description="失败原因。")
    result: dict | None = Field(default=None, description="成功后的摄取摘要。")
    created_at: datetime = Field(..., description="任务创建时间。")
    updated_at: datetime = Field(..., description="最后更新时间。")

    @classmethod
    def from_job(cls, job: IngestJob) -> "IngestJobPayload":
        return cls(
            job_id=job.id,
            filename=job.filename,
            status=job.status,
            stage=job.stage,
            progress=job.progress,
            error=job.error,
            result=job.result,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )
