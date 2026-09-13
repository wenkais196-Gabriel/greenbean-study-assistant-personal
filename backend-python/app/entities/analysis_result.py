from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

from app.enums.analysis_type import AnalysisType


class AnalysisResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()), description="分析结果唯一 ID。")
    document_id: str = Field(..., description="被分析的文档 ID。")
    section_id: str | None = Field(default=None, description="小节解析对应的小节 ID。")
    analysis_type: AnalysisType = Field(..., description="分析范围：全文解析或小节解析。")
    language: str = Field(..., description="分析结果语言。")
    content_markdown: str = Field(..., description="用于展示的 Markdown 内容。")
    summary: str | None = Field(default=None, description="分析结果摘要，供列表展示（可空）。")
    content_json: dict[str, Any] | None = Field(default=None, description="供程序读取的结构化分析内容。")
    model_name: str | None = Field(default=None, description="生成结果使用的 AI 模型名称。")
    prompt_version: str | None = Field(default=None, description="生成结果使用的提示词模板版本。")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="创建时间。")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="最后更新时间。")

    @model_validator(mode="after")
    def validate_analysis_scope(self) -> "AnalysisResult":
        if self.analysis_type == AnalysisType.SECTION and not self.section_id:
            raise ValueError("小节解析必须提供 section_id")
        if self.analysis_type == AnalysisType.FULL_DOCUMENT and self.section_id is not None:
            raise ValueError("全文解析不能设置 section_id")
        return self
