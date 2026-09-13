from sqlalchemy.orm import Session

from app.db.models import DocumentRecordModel
from app.entities import DocumentRecord
from app.repositories.sqlite_helpers import datetime_value, enum_value


class DocumentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def save(self, document: DocumentRecord) -> DocumentRecord:
        model = self.session.get(DocumentRecordModel, document.id)
        if model is None:
            model = DocumentRecordModel(
                id=document.id,
                created_at=datetime_value(document.created_at),
            )
            self.session.add(model)
        model.workspace_id = document.workspace_id
        model.title = document.title
        model.original_filename = document.original_filename
        model.file_type = enum_value(document.file_type)
        model.file_path = document.file_path
        model.file_hash = document.file_hash
        model.status = enum_value(document.status)
        model.page_count = document.page_count
        model.updated_at = datetime_value(document.updated_at)
        return document

    def get_by_id(self, document_id: str) -> DocumentRecord | None:
        model = self.session.get(DocumentRecordModel, document_id)
        if model is None:
            return None
        return self._to_entity(model)

    def list_all(self) -> list[DocumentRecord]:
        """全部文档，按创建时间**倒序**（新的在前）—— 供界面左侧列表使用。

        **不按 workspace 过滤**：上传落库的 `workspace_id` 是 `""`，而会话落库用的是
        `"default"`，两者并不一致 —— 按它过滤会把所有文档都滤掉。详见
        `app/services/document_query_service.py` 的模块说明。
        """
        models = (
            self.session.query(DocumentRecordModel)
            .order_by(DocumentRecordModel.created_at.desc())
            .all()
        )
        return [self._to_entity(model) for model in models]

    @staticmethod
    def _to_entity(model: DocumentRecordModel) -> DocumentRecord:
        return DocumentRecord(
            id=model.id,
            workspace_id=model.workspace_id,
            title=model.title,
            original_filename=model.original_filename,
            file_type=model.file_type,
            file_path=model.file_path,
            file_hash=model.file_hash,
            status=model.status,
            page_count=model.page_count,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
