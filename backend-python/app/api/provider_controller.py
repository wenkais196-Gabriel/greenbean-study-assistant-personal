"""
Provider 配置接口：`/api/providers` —— 列出 / 新增 / 更新 / 删除 / 激活模型配置。

为什么需要它：问答链路从 `ProviderRegistry` 取当前激活的 provider，而在这之前
**没有任何 HTTP 途径**能激活一个 —— 界面只能一直显示"尚未配置可用的模型"。

两条硬约束：
- 响应**永不包含 `api_key`**（`ProviderConfigResponse` 里就没有这个字段）；
- 同一个 `name` 重复 → 409，而不是让数据库唯一约束变成 500。

`ProviderController` 类保留给类风格的调用方（既有测试与 provider workflow），
它与下面的路由共用同一组响应映射函数，不存在第二份逻辑。
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from fastapi.concurrency import run_in_threadpool

from app.db.runtime import lazy_session_factory
from app.db.unit_of_work import SqlAlchemyUnitOfWork
from app.entities.provider_config import ProviderConfig
from app.schemas.provider_schema import (
    ProviderActivateResponse,
    ProviderConfigCreateRequest,
    ProviderConfigResponse,
    ProviderConfigUpdateRequest,
)
from app.services.provider_service import ProviderNameConflictError, ProviderService

router = APIRouter(prefix="/providers", tags=["Providers"])

_RESPONSE_404_NOT_FOUND = {
    http_status.HTTP_404_NOT_FOUND: {"description": "模型配置不存在"}
}
_RESPONSE_409_CONFLICT = {
    http_status.HTTP_409_CONFLICT: {"description": "配置名已存在"}
}
_RESPONSE_404_AND_409 = {**_RESPONSE_404_NOT_FOUND, **_RESPONSE_409_CONFLICT}


def to_provider_response(config: ProviderConfig) -> ProviderConfigResponse:
    """实体 → 响应模型（**不含 `api_key`**，界面不需要、也不该拿到）。"""
    return ProviderConfigResponse(
        id=config.id,
        name=config.name,
        api_mode=config.api_mode,
        api_host=config.api_host,
        api_path=config.api_path,
        model_id=config.model_id,
        display_name=config.display_name,
        context_window=config.context_window,
        max_output_tokens=config.max_output_tokens,
        is_active=config.is_active,
        created_at=config.created_at.isoformat(),
        updated_at=config.updated_at.isoformat(),
    )


def to_activate_response(config: ProviderConfig) -> ProviderActivateResponse:
    """激活结果用更小的结构：界面只需要知道"现在是哪个模型在回答"。"""
    return ProviderActivateResponse(
        id=config.id,
        name=config.name,
        display_name=config.display_name,
        model_id=config.model_id,
    )


class ProviderController:
    """类风格的 provider 编排（保留：既有调用方按这个签名使用）。"""

    def __init__(self, service: ProviderService) -> None:
        self.service = service

    async def list_providers(self) -> list[ProviderConfigResponse]:
        configs = self.service.list_all()
        return [self._to_response(c) for c in configs]

    async def get_provider(self, config_id: str) -> ProviderConfigResponse | None:
        config = self.service.get_by_id(config_id)
        if config is None:
            return None
        return self._to_response(config)

    async def create_provider(self, request: ProviderConfigCreateRequest) -> ProviderConfigResponse:
        config = self.service.create(request.model_dump())
        return self._to_response(config)

    async def update_provider(
        self, config_id: str, request: ProviderConfigUpdateRequest
    ) -> ProviderConfigResponse | None:
        config = self.service.update(config_id, request.model_dump(exclude_none=True))
        if config is None:
            return None
        return self._to_response(config)

    async def delete_provider(self, config_id: str) -> bool:
        return self.service.delete(config_id)

    async def activate_provider(self, config_id: str) -> ProviderActivateResponse | None:
        config = self.service.activate(config_id)
        if config is None:
            return None
        return to_activate_response(config)

    async def get_active_provider(self) -> ProviderActivateResponse | None:
        config = self.service.get_active()
        if config is None:
            return None
        return to_activate_response(config)

    def _to_response(self, config: ProviderConfig) -> ProviderConfigResponse:
        return to_provider_response(config)


def get_provider_controller() -> ProviderController:
    """依赖注入：装配生产库的 `ProviderService`（构造时不建库，第一次用才建）。"""
    return ProviderController(
        ProviderService(SqlAlchemyUnitOfWork(lazy_session_factory()))
    )


@router.get("", response_model=list[ProviderConfigResponse])
async def list_providers(
    controller: Annotated[ProviderController, Depends(get_provider_controller)],
) -> list[ProviderConfigResponse]:
    """列出所有模型配置（含是否当前激活）。"""
    configs = await run_in_threadpool(controller.service.list_all)
    return [to_provider_response(config) for config in configs]


@router.get(
    "/active",
    response_model=ProviderActivateResponse,
    responses=_RESPONSE_404_NOT_FOUND,
)
async def get_active_provider(
    controller: Annotated[ProviderController, Depends(get_provider_controller)],
) -> ProviderActivateResponse:
    """当前激活的模型配置；一个都没配好时 404（界面据此提示去配置）。"""
    config = await run_in_threadpool(controller.service.get_active)
    if config is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="当前没有激活的模型配置",
        )
    return to_activate_response(config)


@router.get(
    "/{config_id}",
    response_model=ProviderConfigResponse,
    responses=_RESPONSE_404_NOT_FOUND,
)
async def get_provider(
    config_id: str,
    controller: Annotated[ProviderController, Depends(get_provider_controller)],
) -> ProviderConfigResponse:
    """按 ID 取单个配置。"""
    config = await run_in_threadpool(controller.service.get_by_id, config_id)
    if config is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"模型配置不存在: {config_id}",
        )
    return to_provider_response(config)


@router.post(
    "",
    response_model=ProviderConfigResponse,
    status_code=http_status.HTTP_201_CREATED,
    responses=_RESPONSE_409_CONFLICT,
)
async def create_provider(
    request: ProviderConfigCreateRequest,
    controller: Annotated[ProviderController, Depends(get_provider_controller)],
) -> ProviderConfigResponse:
    """新增模型配置。新配置**不会**自动激活（避免悄悄换掉正在用的模型）。"""
    try:
        config = await run_in_threadpool(controller.service.create, request.model_dump())
    except ProviderNameConflictError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    return to_provider_response(config)


@router.put(
    "/{config_id}",
    response_model=ProviderConfigResponse,
    responses=_RESPONSE_404_AND_409,
)
async def update_provider(
    config_id: str,
    request: ProviderConfigUpdateRequest,
    controller: Annotated[ProviderController, Depends(get_provider_controller)],
) -> ProviderConfigResponse:
    """局部更新：只改传进来的字段（`None` 的字段保持原值）。"""
    try:
        config = await run_in_threadpool(
            controller.service.update,
            config_id,
            request.model_dump(exclude_none=True),
        )
    except ProviderNameConflictError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    if config is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"模型配置不存在: {config_id}",
        )
    return to_provider_response(config)


@router.post(
    "/{config_id}/activate",
    response_model=ProviderActivateResponse,
    responses=_RESPONSE_404_NOT_FOUND,
)
async def activate_provider(
    config_id: str,
    controller: Annotated[ProviderController, Depends(get_provider_controller)],
) -> ProviderActivateResponse:
    """把某个配置设为当前模型：之后 `POST /api/chat` 不再 503。"""
    config = await run_in_threadpool(controller.service.activate, config_id)
    if config is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"模型配置不存在: {config_id}",
        )
    return to_activate_response(config)


@router.delete(
    "/{config_id}",
    status_code=http_status.HTTP_204_NO_CONTENT,
    responses=_RESPONSE_404_NOT_FOUND,
)
async def delete_provider(
    config_id: str,
    controller: Annotated[ProviderController, Depends(get_provider_controller)],
) -> None:
    """删除配置；删掉的若是当前激活项，registry 会一并清空（回到"未配置"）。"""
    deleted = await run_in_threadpool(controller.service.delete, config_id)
    if not deleted:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"模型配置不存在: {config_id}",
        )
