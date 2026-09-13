from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.enums.message_role import MessageRole


class HistoryMessage(BaseModel):
    role: str = Field(..., description="消息角色：'user' 或 'agent'。")
    content: str = Field(..., description="消息内容。")


ChatMessage = HistoryMessage


class ChatRequest(BaseModel):
    session_id: str = Field(..., description="会话 ID，用于关联对话历史。")
    query: str = Field(..., description="用户当前提出的问题。")
    history: list[HistoryMessage] = Field(default_factory=list, description="对话历史记录。")
    use_extended_context: bool = Field(default=False, description="是否包含小节解析和历史摘要上下文。")
    workspace_id: str | None = Field(
        default=None,
        description="会话归属的工作区；留空时由后端归入默认工作区。",
    )


class ChatUsage(BaseModel):
    """一次回答的 token 用量；provider 回传才拿得到，拿不到时字段为 None。

    口径：只统计**回答**那次 LLM 调用。路由那次是内部决策开销，别的账去算。
    """

    input_tokens: int | None = Field(default=None, description="输入 token 数（prompt）。")
    output_tokens: int | None = Field(default=None, description="输出 token 数（completion）。")


class ChatResponse(BaseModel):
    session_id: str = Field(..., description="会话 ID。")
    answer: str = Field(..., description="AI 生成的回答。")
    source_context: list[dict[str, Any]] | None = Field(default=None, description="回答引用的检索上下文。")
    trace_id: str | None = Field(
        default=None,
        description="本次链路的追踪 ID，可用 GET /api/traces/{trace_id} 取回全部 span。",
    )
    usage: ChatUsage | None = Field(
        default=None,
        description="回答那次 LLM 调用的 token 用量；provider 不回传时为 null。",
    )


class ChatSessionCreateRequest(BaseModel):
    workspace_id: str = Field(..., description="所属工作区 ID。")
    document_id: str | None = Field(default=None, description="关联文档 ID；工作区级会话时留空。")
    title: str = Field(..., description="会话标题。")


class ChatSessionResponse(BaseModel):
    id: str = Field(..., description="会话 ID。")
    workspace_id: str = Field(..., description="所属工作区 ID。")
    document_id: str | None = Field(default=None, description="关联文档 ID。")
    title: str = Field(..., description="会话标题。")
    created_at: datetime = Field(..., description="创建时间。")
    updated_at: datetime = Field(..., description="最后更新时间。")


class ChatMessageResponse(BaseModel):
    id: str = Field(..., description="消息 ID。")
    session_id: str = Field(..., description="所属会话 ID。")
    role: MessageRole = Field(..., description="消息角色。")
    content: str = Field(..., description="消息正文。")
    source_context_json: dict[str, Any] | None = Field(default=None, description="回答引用的检索上下文。")
    created_at: datetime = Field(..., description="创建时间。")
