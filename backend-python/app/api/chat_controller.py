"""
聊天接口控制器：`POST /api/chat` —— 提问 → 检索 → 带来源的回答。
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status

from app.db.runtime import lazy_session_factory
from app.providers.registry import ProviderNotFoundError
from app.schemas.chat_schema import ChatRequest, ChatResponse
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["Chat"])

# ---- 错误响应定义（供 @router 装饰器复用） ----
_RESPONSE_400_BAD_REQUEST = {
    http_status.HTTP_400_BAD_REQUEST: {"description": "请求参数无效"}
}
_RESPONSE_503_UNAVAILABLE = {
    http_status.HTTP_503_SERVICE_UNAVAILABLE: {
        "description": "尚未配置可用的模型 provider"
    }
}
_RESPONSE_400_AND_503 = {**_RESPONSE_400_BAD_REQUEST, **_RESPONSE_503_UNAVAILABLE}


def get_chat_service() -> ChatService:
    """依赖注入：会话工厂懒加载（见 app/db/runtime），构造时不碰磁盘。"""
    return ChatService(session_factory=lazy_session_factory())


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
