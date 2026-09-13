"""
DocumentQueryService 单元测试：文档列表与文档单元查询的编排。

repository 被替换成假对象 —— 这里只验证 service 的两件事：
**未知文档要能被区分出来**（返回 None，由控制器翻成 404），以及结果原样透出。
SQL 层的排序契约由 `tests/integration/persistence/test_sqlite_repositories.py`
在真库上锁定（两边职责不同，不是重复）。
"""
from unittest.mock import MagicMock, patch

import pytest

from app.services.document_query_service import DocumentQueryService


@pytest.fixture
def mock_session():
    """`with session_factory() as session` 用 MagicMock 就能满足。"""
    return MagicMock()


def make_service(mock_session) -> DocumentQueryService:
    return DocumentQueryService(session_factory=lambda: mock_session)


class TestListDocuments:
    @patch("app.services.document_query_service.DocumentRepository")
    def test_delegates_to_repository(self, MockRepository, mock_session):
        records = [MagicMock(), MagicMock()]
        MockRepository.return_value.list_all.return_value = records

        result = make_service(mock_session).list_documents()

        assert result is records
        MockRepository.return_value.list_all.assert_called_once_with()


class TestListUnits:
    @patch("app.services.document_query_service.DocumentUnitRepository")
    @patch("app.services.document_query_service.DocumentRepository")
    def test_returns_units_for_existing_document(
        self, MockDocumentRepository, MockUnitRepository, mock_session
    ):
        MockDocumentRepository.return_value.get_by_id.return_value = MagicMock()
        units = [MagicMock()]
        MockUnitRepository.return_value.list_by_document.return_value = units

        result = make_service(mock_session).list_units("doc-1")

        assert result is units
        MockDocumentRepository.return_value.get_by_id.assert_called_once_with("doc-1")
        MockUnitRepository.return_value.list_by_document.assert_called_once_with("doc-1")

    @patch("app.services.document_query_service.DocumentUnitRepository")
    @patch("app.services.document_query_service.DocumentRepository")
    def test_returns_none_for_unknown_document(
        self, MockDocumentRepository, MockUnitRepository, mock_session
    ):
        """文档不存在 → None（控制器据此回 404），且不去查单元。"""
        MockDocumentRepository.return_value.get_by_id.return_value = None

        result = make_service(mock_session).list_units("nope")

        assert result is None
        MockUnitRepository.return_value.list_by_document.assert_not_called()
