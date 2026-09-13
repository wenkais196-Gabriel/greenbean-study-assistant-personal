"""
文档查询接口测试：`GET /api/documents`（文档列表）与
`GET /api/documents/{document_id}/units`（文档单元内容）。

控制器只负责 HTTP 契约（状态码 / 响应形状 / 404 映射 / snake_case 投影），
查询语义由 `DocumentQueryService` 与 repository 各自测试覆盖。
这里注入假 service —— 与 `test_document_controller.py` 的写法保持一致。

响应沿用同控制器既有两个端点的 `{code, message, data}` 包裹，
前端因此只用一套解包逻辑（`upload.ts` 已经这么读）。
"""
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.document_controller import get_document_query_service
from app.entities import DocumentRecord, DocumentUnit
from app.enums import DocumentFileType, DocumentStatus
from app.main import app
from app.services.document_query_service import DocumentQueryService


def make_document(**overrides) -> DocumentRecord:
    values = {
        "id": "doc-1",
        "workspace_id": "",
        "title": "cours-analyse-s1",
        "original_filename": "cours-analyse-s1.pdf",
        "file_type": DocumentFileType.PDF,
        "file_path": "data/uploads/cours-analyse-s1.pdf",
        "status": DocumentStatus.PARSED,
        "page_count": 12,
    }
    values.update(overrides)
    return DocumentRecord(**values)


def make_unit(**overrides) -> DocumentUnit:
    values = {
        "id": "unit-1",
        "document_id": "doc-1",
        "sequence_index": 0,
        "text_content": "Chapitre 1 : introduction",
        "page_number": 1,
    }
    values.update(overrides)
    return DocumentUnit(**values)


@pytest.fixture(autouse=True)
def reset_query_service_singleton():
    """`get_document_query_service` 是进程内单例：测试之间必须清掉，避免互相污染。"""
    get_document_query_service.cache_clear()
    yield
    get_document_query_service.cache_clear()


@pytest.mark.us25
def test_get_document_query_service_returns_a_singleton():
    """依赖注入工厂：进程内复用同一个实例（会话工厂懒加载，构造时不建库）。"""
    service = get_document_query_service()

    assert isinstance(service, DocumentQueryService)
    assert get_document_query_service() is service


class TestListDocuments:
    """`GET /api/documents`"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = TestClient(app)
        self.mock_service = MagicMock()
        app.dependency_overrides[get_document_query_service] = lambda: self.mock_service
        yield
        app.dependency_overrides.clear()

    @pytest.mark.us25
    def test_returns_summaries_in_service_order(self):
        """列表原样透出 service 给的顺序，并投影出前端需要的字段。"""
        older = make_document(id="doc-1", title="旧文档")
        newer = make_document(id="doc-2", title="新文档")
        self.mock_service.list_documents.return_value = [newer, older]

        response = self.client.get("/api/documents")

        assert response.status_code == 200
        payload = response.json()
        assert payload["code"] == 200
        documents = payload["data"]
        assert [item["document_id"] for item in documents] == ["doc-2", "doc-1"]
        assert documents[0]["title"] == "新文档"
        assert documents[0]["original_filename"] == "cours-analyse-s1.pdf"
        assert documents[0]["file_type"] == "pdf"
        assert documents[0]["status"] == "parsed"
        assert documents[0]["page_count"] == 12
        assert documents[0]["created_at"]

    @pytest.mark.us25
    def test_returns_empty_array_when_nothing_uploaded(self):
        """一份文档都没有 → 200 + 空数组（不是 404）。"""
        self.mock_service.list_documents.return_value = []

        response = self.client.get("/api/documents")

        assert response.status_code == 200
        assert response.json()["data"] == []

    @pytest.mark.us25
    def test_unknown_page_count_is_passed_through(self):
        """页数未知（None）原样返回，由前端决定怎么显示。"""
        self.mock_service.list_documents.return_value = [make_document(page_count=None)]

        response = self.client.get("/api/documents")

        assert response.json()["data"][0]["page_count"] is None


class TestListDocumentUnits:
    """`GET /api/documents/{document_id}/units`"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = TestClient(app)
        self.mock_service = MagicMock()
        app.dependency_overrides[get_document_query_service] = lambda: self.mock_service
        yield
        app.dependency_overrides.clear()

    @pytest.mark.us25
    def test_returns_units_with_source_page_numbers(self):
        """单元按 service 给的顺序透出，带正文与页码。"""
        self.mock_service.list_units.return_value = [
            make_unit(id="unit-1", sequence_index=0, page_number=1, text_content="第一页"),
            make_unit(id="unit-2", sequence_index=1, page_number=2, text_content="第二页"),
        ]

        response = self.client.get("/api/documents/doc-1/units")

        assert response.status_code == 200
        units = response.json()["data"]
        assert [unit["unit_id"] for unit in units] == ["unit-1", "unit-2"]
        assert units[0]["sequence_index"] == 0
        assert units[0]["page_number"] == 1
        assert units[0]["text_content"] == "第一页"
        # 解析器的原始布局体积大且界面不用，不进响应
        assert "raw_content_json" not in units[0]

    @pytest.mark.us25
    def test_unknown_document_returns_404(self):
        self.mock_service.list_units.return_value = None

        response = self.client.get("/api/documents/nope/units")

        assert response.status_code == 404
        assert "nope" in response.json()["detail"]

    @pytest.mark.us25
    def test_document_without_units_returns_empty_array(self):
        self.mock_service.list_units.return_value = []

        response = self.client.get("/api/documents/doc-1/units")

        assert response.status_code == 200
        assert response.json()["data"] == []

    @pytest.mark.us25
    def test_unit_without_page_number_is_passed_through(self):
        """拿不到页码的单元照样返回，前端据此给出可读提示。"""
        self.mock_service.list_units.return_value = [make_unit(page_number=None)]

        response = self.client.get("/api/documents/doc-1/units")

        assert response.json()["data"][0]["page_number"] is None
