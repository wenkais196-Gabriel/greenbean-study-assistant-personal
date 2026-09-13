"""
界面只读查询：文档列表与某份文档的内容单元。

与 `DocumentIngestService`（写侧）分开 —— 这里只有读，没有事务边界上的副作用，
也不需要 trace / 进度回调。

⚠️ **不按 workspace 过滤**：上传落库时 `document_records.workspace_id` 是 `""`
（`document_controller.upload_document` → `job_service.submit(filename, content)` 没传
`workspace_id`），而会话落库用的是 `chat_session_service.DEFAULT_WORKSPACE_ID = "default"`。
两边并不一致，本地单机场景下按 workspace 过滤只会把全部文档都滤掉。
工作区归属的统一留待单独处理（见 STATUS 的待办），这里不做半套过滤。
"""
from app.db.orm import SessionFactory
from app.entities import DocumentRecord, DocumentUnit
from app.repositories.document_repository import DocumentRepository
from app.repositories.document_unit_repository import DocumentUnitRepository


class DocumentQueryService:
    def __init__(self, session_factory: SessionFactory) -> None:
        self.session_factory = session_factory

    def list_documents(self) -> list[DocumentRecord]:
        """全部文档，按上传时间倒序（新的在前）。"""
        with self.session_factory() as session:
            return DocumentRepository(session).list_all()

    def list_units(self, document_id: str) -> list[DocumentUnit] | None:
        """返回某份文档的内容单元（按文档内顺序）。

        **文档不存在时返回 `None`** —— 由控制器翻成 404；文档存在但没有单元是
        正常情况，返回空列表。订阅这个区别，界面才能区分"这份文档不存在"和"这份
        文档解析后没有内容"。
        """
        with self.session_factory() as session:
            if DocumentRepository(session).get_by_id(document_id) is None:
                return None
            return DocumentUnitRepository(session).list_by_document(document_id)
