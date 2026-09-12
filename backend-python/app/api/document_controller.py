"""
文档接口控制器，提供文档上传、列表和详情相关 API。
"""
from typing import Annotated

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi import status as http_status
from fastapi.concurrency import run_in_threadpool

from app.db.runtime import lazy_session_factory
from app.services.document_ingest_service import DocumentIngestService
from app.utils.file_utils import is_supported, get_extension

router = APIRouter(prefix="/documents", tags=["Documents"])

# ---- 错误响应定义（供 @router 装饰器复用） ----
_RESPONSE_400_BAD_REQUEST = {
    http_status.HTTP_400_BAD_REQUEST: {"description": "请求参数无效"}
}
_RESPONSE_500_INTERNAL_ERROR = {
    http_status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "服务器内部错误"}
}
_RESPONSE_400_AND_500 = {**_RESPONSE_400_BAD_REQUEST, **_RESPONSE_500_INTERNAL_ERROR}

# 支持的格式描述信息，供错误提示复用
_SUPPORTED_FORMATS_MSG = (
    "PDF(.pdf), Word(.docx), PPT(.pptx), 纯文本(.txt/.md), 图片(.jpg/.jpeg/.png/.webp)"
)


def get_ingest_service() -> DocumentIngestService:
    """依赖注入：每个请求拿一个 IngestService；会话工厂懒加载（见 app/db/runtime）。

    注入 session_factory 即开启**完整摄取**：解析 → 落库 → 切块 → 向量化。
    """
    return DocumentIngestService(session_factory=lazy_session_factory())


@router.post(
    "/upload",
    responses=_RESPONSE_400_AND_500,
)
async def upload_document(
    file: Annotated[UploadFile, File(...)],
    ingest_service: Annotated[DocumentIngestService, Depends(get_ingest_service)],
):
    """
    接收前端通过 FormData 传来的文件，调用 Service 流水线进行解析与导入。
    
    支持的文件格式:
    - 文档: PDF(.pdf), Word(.docx), PPT(.pptx), 纯文本(.txt/.md)
    - 图片: JPG/JPEG, PNG, WEBP
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
    
    try:
        # 读取文件二进制流
        file_content = await file.read()
        
        # 检查文件是否为空
        if not file_content:
            raise HTTPException(status_code=400, detail="文件内容为空")
        
        # 进入导入流水线：解析 + 落库 + 切块 + 向量化是**同步且可能耗时**的
        # （e5 嵌入实测约 200 ms/片段），必须放线程池，否则会阻塞事件循环、拖垮整个服务。
        result = await run_in_threadpool(
            ingest_service.ingest_document, file.filename, file_content
        )
        
        return {
            "code": 200,
            "message": "文件上传并解析成功",
            "data": result,
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
