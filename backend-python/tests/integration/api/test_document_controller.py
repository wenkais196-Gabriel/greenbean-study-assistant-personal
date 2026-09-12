"""
文档接口控制器测试：上传受理（202）与任务查询（200 / 404）、以及全部同步校验。

上传已**异步化**（见 docs/specs/us-stage1-upload-async.md）：控制器不再返回摄取结果，
只返回受理回执；摄取结果通过 `GET /api/documents/jobs/{job_id}` 查询。
这里注入假 job service，覆盖的是控制器的 HTTP 契约，不是摄取本身。
"""
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient

from app.api.document_controller import get_job_service, upload_document
from app.entities import IngestJob
from app.enums import IngestJobStatus, IngestStage
from app.main import app
from app.services.ingest_job_service import IngestJobService


def _create_test_file(content: bytes, filename: str, content_type: str = "application/octet-stream"):
    """创建测试用 UploadFile 模拟数据 - 使用 (filename, content, content_type) 元组格式"""
    return {"file": (filename, content, content_type)}


@pytest.fixture(autouse=True)
def reset_job_service_singleton():
    """`get_job_service` 是进程内单例：测试之间必须清掉，避免互相污染。"""
    get_job_service.cache_clear()
    yield
    get_job_service.cache_clear()


@pytest.mark.us25
def test_get_job_service_returns_a_singleton():
    """依赖注入工厂：进程内复用同一个实例（内含线程池与懒加载会话工厂）。"""
    service = get_job_service()

    assert isinstance(service, IngestJobService)
    assert get_job_service() is service


class TestDocumentUpload:
    """文档上传接口测试"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """每个测试前重置依赖注入"""
        self.client = TestClient(app)
        self.mock_job_service = MagicMock()
        self.mock_job_service.submit.return_value = IngestJob(
            id="job-1", filename="test.pdf"
        )

        def mock_get_job_service():
            return self.mock_job_service

        app.dependency_overrides[get_job_service] = mock_get_job_service
        yield
        app.dependency_overrides.clear()

    @pytest.mark.us25
    def test_upload_pdf_is_accepted(self):
        """上传 PDF：立即受理并给出 job_id（不等摄取）"""
        files = _create_test_file(b"%PDF-1.4 fake content", "test.pdf")
        response = self.client.post("/api/documents/upload", files=files)

        assert response.status_code == 202
        data = response.json()
        assert data["code"] == 202
        assert data["data"]["job_id"] == "job-1"
        assert data["data"]["status"] == "queued"
        assert data["data"]["filename"] == "test.pdf"
        assert data["data"]["progress"] == 0.0
        self.mock_job_service.submit.assert_called_once()

    @pytest.mark.us25
    def test_upload_docx_is_accepted(self):
        """上传 Word 文档"""
        files = _create_test_file(b"fake docx content", "notes.docx")
        response = self.client.post("/api/documents/upload", files=files)

        assert response.status_code == 202

    @pytest.mark.us25
    @pytest.mark.parametrize(
        "filename", ["photo.png", "photo.jpg", "photo.jpeg", "image.webp"]
    )
    def test_upload_images_are_accepted(self, filename):
        """图片格式（含 OCR 路径）都走同一条受理逻辑"""
        files = _create_test_file(b"fake image content", filename)
        response = self.client.post("/api/documents/upload", files=files)

        assert response.status_code == 202

    @pytest.mark.us25
    def test_upload_unsupported_format(self):
        """测试上传不支持的文件格式：同步拒绝，且不创建 job"""
        files = _create_test_file(b"content", "file.ppt")
        response = self.client.post("/api/documents/upload", files=files)

        assert response.status_code == 400
        assert "暂不支持" in response.json()["detail"]
        self.mock_job_service.submit.assert_not_called()

    @pytest.mark.us25
    def test_upload_empty_filename(self):
        """测试上传文件名为空 - FastAPI 校验返回 422"""
        files = {"file": ("", b"content", "application/octet-stream")}
        response = self.client.post("/api/documents/upload", files=files)

        assert response.status_code == 422
        self.mock_job_service.submit.assert_not_called()

    @pytest.mark.us25
    def test_upload_filename_none(self):
        """测试文件名为 None 时触发控制器内的空文件名检查"""
        async def _run():
            mock_file = MagicMock(spec=UploadFile)
            mock_file.filename = None
            mock_file.read = AsyncMock(return_value=b"content")

            with pytest.raises(HTTPException) as exc_info:
                await upload_document(file=mock_file, job_service=self.mock_job_service)

            assert exc_info.value.status_code == 400
            assert "文件名不能为空" in exc_info.value.detail

        asyncio.run(_run())

    @pytest.mark.us25
    def test_upload_empty_content(self):
        """测试上传空文件"""
        files = _create_test_file(b"", "empty.pdf")
        response = self.client.post("/api/documents/upload", files=files)

        assert response.status_code == 400
        assert "文件内容为空" in response.json()["detail"]
        self.mock_job_service.submit.assert_not_called()

    @pytest.mark.us25
    def test_upload_value_error_maps_to_400(self):
        """受理阶段抛业务异常 → 400（而不是 500 堆栈）"""
        self.mock_job_service.submit.side_effect = ValueError("业务异常")

        files = _create_test_file(b"content", "test.pdf")
        response = self.client.post("/api/documents/upload", files=files)

        assert response.status_code == 400
        assert "业务异常" in response.json()["detail"]

    @pytest.mark.us25
    def test_upload_passes_through_already_handled_http_exception(self):
        """已经是 HTTPException 的错误不再被包装：状态码与提示原样透出"""
        self.mock_job_service.submit.side_effect = HTTPException(
            status_code=409, detail="任务冲突"
        )

        files = _create_test_file(b"content", "test.pdf")
        response = self.client.post("/api/documents/upload", files=files)

        assert response.status_code == 409
        assert "任务冲突" in response.json()["detail"]

    @pytest.mark.us25
    def test_upload_unexpected_error_maps_to_500(self):
        """未知异常 → 500 + 可读提示"""
        self.mock_job_service.submit.side_effect = Exception("未知错误")

        files = _create_test_file(b"content", "test.pdf")
        response = self.client.post("/api/documents/upload", files=files)

        assert response.status_code == 500
        assert "文件处理失败" in response.json()["detail"]


class TestIngestJobStatus:
    """任务查询接口测试"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = TestClient(app)
        self.mock_job_service = MagicMock()

        app.dependency_overrides[get_job_service] = lambda: self.mock_job_service
        yield
        app.dependency_overrides.clear()

    @pytest.mark.us25
    def test_get_job_returns_progress_payload(self):
        self.mock_job_service.get.return_value = IngestJob(
            id="job-9",
            filename="cours.pdf",
            status=IngestJobStatus.RUNNING,
            stage=IngestStage.EMBEDDING,
            progress=0.575,
        )

        response = self.client.get("/api/documents/jobs/job-9")

        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["job_id"] == "job-9"
        assert payload["status"] == "running"
        assert payload["stage"] == "embedding"
        assert payload["progress"] == 0.575

    @pytest.mark.us25
    def test_get_unknown_job_returns_404(self):
        self.mock_job_service.get.return_value = None

        response = self.client.get("/api/documents/jobs/nope")

        assert response.status_code == 404
        assert "nope" in response.json()["detail"]

    @pytest.mark.us25
    def test_succeeded_job_exposes_the_result_summary(self):
        self.mock_job_service.get.return_value = IngestJob(
            id="job-10",
            filename="cours.pdf",
            status=IngestJobStatus.SUCCEEDED,
            stage=IngestStage.EMBEDDING,
            progress=1.0,
            result={"chunks_created": 7, "document_id": "doc-1"},
        )

        response = self.client.get("/api/documents/jobs/job-10")

        payload = response.json()["data"]
        assert payload["result"] == {"chunks_created": 7, "document_id": "doc-1"}
        assert payload["error"] is None
