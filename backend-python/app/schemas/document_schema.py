"""文档查询接口的 Schema：界面要读的**文档摘要**与**文档单元原文**。"""
from datetime import datetime

from pydantic import BaseModel, Field

from app.entities import DocumentRecord, DocumentUnit
from app.enums import DocumentFileType, DocumentStatus


class DocumentSummaryPayload(BaseModel):
    """文档列表里的一条。

    主键字段叫 `document_id` 而不是 `id`：它会在前端状态与 URL 里流转，
    取名理由与 `IngestJobPayload.job_id` 一致。
    """

    document_id: str = Field(..., description="文档 ID。")
    title: str = Field(..., description="文档显示标题。")
    original_filename: str = Field(..., description="用户上传时的原始文件名。")
    file_type: DocumentFileType = Field(..., description="文档文件类型。")
    status: DocumentStatus = Field(..., description="文档处理状态。")
    page_count: int | None = Field(default=None, description="页数；未知为 None。")
    created_at: datetime = Field(..., description="上传时间。")

    @classmethod
    def from_record(cls, record: DocumentRecord) -> "DocumentSummaryPayload":
        return cls(
            document_id=record.id,
            title=record.title,
            original_filename=record.original_filename,
            file_type=record.file_type,
            status=record.status,
            page_count=record.page_count,
            created_at=record.created_at,
        )


class DocumentUnitPayload(BaseModel):
    """一份文档里的一页（或一张 slide）的原文。

    **不投影 `raw_content_json`**：解析器的原始布局体积大，界面用不到。
    """

    unit_id: str = Field(..., description="内容单元 ID，也是界面定位用的锚点。")
    sequence_index: int = Field(..., description="文档内的顺序。")
    page_number: int | None = Field(default=None, description="来源页码；拿不到为 None。")
    text_content: str = Field(..., description="统一正文。")

    @classmethod
    def from_unit(cls, unit: DocumentUnit) -> "DocumentUnitPayload":
        return cls(
            unit_id=unit.id,
            sequence_index=unit.sequence_index,
            page_number=unit.page_number,
            text_content=unit.text_content,
        )
