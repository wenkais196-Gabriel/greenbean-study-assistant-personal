"""
聊天接口控制器：`POST /api/chat`（提问 → 检索 → 带来源的回答）与
`GET /api/chat/sessions/{session_id}/messages`（回读会话历史）。
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from fastapi.concurrency import run_in_threadpool

from app.db.runtime import lazy_session_factory
from app.providers.registry import ProviderNotFoundError
from app.schemas.chat_schema import ChatMessageResponse, ChatRequest, ChatResponse
from app.services.chat_service import ChatService
from app.services.trace_recorder import production_trace_recorder

router = APIRouter(prefix="/chat", tags=["Chat"])

# ---- 错误响应定义（供 @router 装饰器复用） ----
_RESPONSE_400_BAD_REQUEST = {
    http_status.HTTP_400_BAD_REQUEST: {"description": "请求参数无效"}
}
_RESPONSE_404_NOT_FOUND = {
    http_status.HTTP_404_NOT_FOUND: {"description": "会话不存在"}
}
_RESPONSE_503_UNAVAILABLE = {
    http_status.HTTP_503_SERVICE_UNAVAILABLE: {
        "description": "尚未配置可用的模型 provider"
    }
}
_RESPONSE_400_AND_503 = {**_RESPONSE_400_BAD_REQUEST, **_RESPONSE_503_UNAVAILABLE}


def get_chat_service() -> ChatService:
    """依赖注入：会话工厂懒加载（见 app/db/runtime），构造时不碰磁盘。

    trace 关闭时 `production_trace_recorder()` 返回 `None`，链路走无 trace 路径
    （见 docs/specs/us-stage1-trace.md AC9）。
    """
    return ChatService(
        session_factory=lazy_session_factory(),
        trace_recorder=production_trace_recorder(),
    )


@router.post(
    "",
    response_model=ChatResponse,
    responses=_RESPONSE_400_AND_503,
)
async def ask(
    request: ChatRequest,
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> ChatResponse:
    """
    按学生提问检索课程资料，并生成**带来源**的回答。

    返回的 `source_context` 与上下文块里的 `[来源 N]` 一一对应，
    前端据此把回答里的引用映射回具体的片段 / 文档 / 页码。
    `trace_id` 可用于 `GET /api/traces/{trace_id}` 取回这次链路的完整 span。
    """
    if not request.query.strip():
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="query 不能为空",
        )

    try:
        return await service.answer(request)
    except ProviderNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"尚未配置可用的模型 provider：{exc}",
        ) from exc


@router.get(
    "/sessions/{session_id}/messages",
    response_model=list[ChatMessageResponse],
    responses=_RESPONSE_404_NOT_FOUND,
)
async def list_session_messages(
    session_id: str,
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> list[ChatMessageResponse]:
    """回读一次会话的历史消息（按时间升序），供刷新或重开界面后恢复对话。"""
    messages = await run_in_threadpool(service.list_session_messages, session_id)
    if messages is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"会话不存在: {session_id}",
        )

    return [
        ChatMessageResponse(
            id=message.id,
            session_id=message.session_id,
            role=message.role,
            content=message.content,
            source_context_json=message.source_context_json,
            created_at=message.created_at,
        )
        for message in messages
    ]
