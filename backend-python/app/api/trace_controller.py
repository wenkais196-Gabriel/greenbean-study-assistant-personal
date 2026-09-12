"""
trace 的读出口：`GET /api/traces/{trace_id}`。

本批**不做**前端 trace 面板（见 docs/specs/us-stage1-trace.md §7），但必须有
"能被查回来"的最小能力 —— 否则 trace 只是写进表里的死数据，谈不上"可查可评测"。
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from fastapi.concurrency import run_in_threadpool

from app.schemas.trace_schema import TracePayload
from app.services.trace_recorder import TraceRecorder, production_trace_recorder

router = APIRouter(prefix="/traces", tags=["Traces"])

_RESPONSE_404_NOT_FOUND = {
    http_status.HTTP_404_NOT_FOUND: {"description": "trace 不存在"}
}


def get_trace_recorder() -> TraceRecorder | None:
    """依赖注入：trace 关闭时 `production_trace_recorder()` 返回 `None`（查询一律 404）。

    开关只在 `production_trace_recorder` 一处判断 —— 多一层判断就多一处会漏改的地方。
    """
    return production_trace_recorder()


@router.get("/{trace_id}", responses=_RESPONSE_404_NOT_FOUND)
async def get_trace(
    trace_id: str,
    recorder: Annotated[TraceRecorder | None, Depends(get_trace_recorder)],
):
    """取回一条 trace 的全部 span（按发生顺序）。"""
    spans = (
        await run_in_threadpool(recorder.get_trace, trace_id)
        if recorder is not None
        else []
    )
    if not spans:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"trace 不存在: {trace_id}",
        )

    return {
        "code": 200,
        "message": "ok",
        "data": TracePayload.from_spans(trace_id, spans).model_dump(mode="json"),
    }
