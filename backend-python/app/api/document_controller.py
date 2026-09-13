"""
文档接口控制器：上传**受理**（202）与上传任务进度查询。

上传已**异步化**（见 docs/specs/us-stage1-upload-async.md）：
大文档摄取要 1~2 分钟，让 HTTP 请求干等既会拖垮体验、也占着连接。
现在请求只负责"校验 + 受理"，摄取交给 `IngestJobService` 在后台线程池里跑，
客户端拿 `job_id` 轮询 `GET /documents/jobs/{job_id}` 看进度。
"""
from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi import status as http_status
from fastapi.concurrency import run_in_threadpool

from app.db.runtime import lazy_session_factory
from app.schemas.document_schema import DocumentSummaryPayload, DocumentUnitPayload
from app.schemas.upload_schema import IngestJobPayload
from app.services.document_ingest_service import DocumentIngestService
from app.services.document_query_service import DocumentQueryService
from app.services.ingest_job_service import IngestJobService
from app.services.trace_recorder import production_trace_recorder
from app.utils.file_utils import is_supported, get_extension

router = APIRouter(prefix="/documents", tags=["Documents"])

# ---- 错误响应定义（供 @router 装饰器复用） ----
_RESPONSE_400_BAD_REQUEST = {
    http_status.HTTP_400_BAD_REQUEST: {"description": "请求参数无效"}
}
_RESPONSE_404_NOT_FOUND = {
    http_status.HTTP_404_NOT_FOUND: {"description": "上传任务不存在"}
}
_RESPONSE_500_INTERNAL_ERROR = {
    http_status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "服务器内部错误"}
}
_RESPONSE_400_AND_500 = {**_RESPONSE_400_BAD_REQUEST, **_RESPONSE_500_INTERNAL_ERROR}
_RESPONSE_404_DOCUMENT_NOT_FOUND = {
    http_status.HTTP_404_NOT_FOUND: {"description": "文档不存在"}
}

# 支持的格式描述信息，供错误提示复用
_SUPPORTED_FORMATS_MSG = (
    "PDF(.pdf), Word(.docx), PPT(.pptx), 纯文本(.txt/.md), 图片(.jpg/.jpeg/.png/.webp)"
)


@lru_cache(maxsize=1)
def get_job_service() -> IngestJobService:
    """依赖注入：取上传任务服务（测试用 `dependency_overrides` 覆盖，或 `cache_clear()` 重置）。

    进程内单例，内含线程池与会话工厂；构造时**不建库**（会话工厂是懒加载的）。
    """
    return IngestJobService(
        session_factory=lazy_session_factory(),
        ingest_service=DocumentIngestService(
            session_factory=lazy_session_factory(),
            trace_recorder=production_trace_recorder(),
        ),
    )


@router.post(
    "/upload",
    status_code=http_status.HTTP_202_ACCEPTED,
    responses=_RESPONSE_400_AND_500,
)
async def upload_document(
    file: Annotated[UploadFile, File(...)],
    job_service: Annotated[IngestJobService, Depends(get_job_service)],
):
    """
    接收前端通过 FormData 传来的文件，**校验后立即受理**，并返回任务 ID。

    支持的文件格式:
    - 文档: PDF(.pdf), Word(.docx), PPT(.pptx), 纯文本(.txt/.md)
    - 图片: JPG/JPEG, PNG, WEBP

    校验失败仍是同步返回（400 / 422），**不会创建任务** —— 参数错误没必要占用后台资源。
    """
    # 检查文件名是否存在
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    # 检查文件格式是否支持
    if not is_supported(file.filename):
        ext = get_extension(file.filename)
        raise HTTPException(
            status_code=400,
            detail=f"暂不支持 {ext} 格式。支持的格式: {_SUPPORTED_FORMATS_MSG}",
        )

    # 读取文件二进制流
    file_content = await file.read()

    # 检查文件是否为空
    if not file_content:
        raise HTTPException(status_code=400, detail="文件内容为空")

    try:
        # 建任务并投递线程池：**同步 DB 写 + 线程池提交**，很快返回，不等摄取跑完
        job = await run_in_threadpool(job_service.submit, file.filename, file_content)

        return {
            "code": http_status.HTTP_202_ACCEPTED,
            "message": "文件已受理，正在解析",
            "data": IngestJobPayload.from_job(job).model_dump(mode="json"),
        }

    except ValueError as ve:
        # 捕获类似"不支持的文件格式"等业务异常
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException:
        # 重新抛出已处理的 HTTP 异常
        raise
    except Exception as e:
        # 捕获系统底层或未知异常
        raise HTTPException(status_code=500, detail=f"文件处理失败: {str(e)}")


@router.get("/jobs/{job_id}", responses=_RESPONSE_404_NOT_FOUND)
async def get_ingest_job(
    job_id: str,
    job_service: Annotated[IngestJobService, Depends(get_job_service)],
):
    """查询一次上传的进度与结果（客户端轮询这个端点）。"""
    job = await run_in_threadpool(job_service.get, job_id)
    if job is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"上传任务不存在: {job_id}",
        )

    return {
        "code": 200,
        "message": "ok",
        "data": IngestJobPayload.from_job(job).model_dump(mode="json"),
    }


@lru_cache(maxsize=1)
def get_document_query_service() -> DocumentQueryService:
    """依赖注入：取文档查询服务（测试用 `dependency_overrides` 覆盖，或 `cache_clear()` 重置）。

    与 `get_job_service` 一致：会话工厂懒加载，构造时**不建库**。
    """
    return DocumentQueryService(session_factory=lazy_session_factory())


@router.get("", responses=_RESPONSE_500_INTERNAL_ERROR)
async def list_documents(
    query_service: Annotated[DocumentQueryService, Depends(get_document_query_service)],
):
    """列出已上传的文档（新的在前），供界面左侧文件列表使用。

    一份文档都没有时返回**空数组**而不是 404 —— "还没上传资料"是正常状态，不是错误。
    """
    records = await run_in_threadpool(query_service.list_documents)

    return {
        "code": 200,
        "message": "ok",
        "data": [
            DocumentSummaryPayload.from_record(record).model_dump(mode="json")
            for record in records
        ],
    }


@router.get("/{document_id}/units", responses=_RESPONSE_404_DOCUMENT_NOT_FOUND)
async def list_document_units(
    document_id: str,
    query_service: Annotated[DocumentQueryService, Depends(get_document_query_service)],
):
    """读取一份文档的内容单元（按文档内顺序）。

    界面用它显示原文，并按 AI 回答里的引用页码定位到对应页。
    """
    units = await run_in_threadpool(query_service.list_units, document_id)
    if units is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"文档不存在: {document_id}",
        )

    return {
        "code": 200,
        "message": "ok",
        "data": [DocumentUnitPayload.from_unit(unit).model_dump(mode="json") for unit in units],
    }
