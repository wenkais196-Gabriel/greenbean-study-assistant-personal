from sqlalchemy.orm import Session

from app.db.models import DocumentUnitModel
from app.entities import DocumentUnit
from app.repositories.sqlite_helpers import datetime_value, json_object, json_value


class DocumentUnitRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def save(self, unit: DocumentUnit) -> DocumentUnit:
        model = self.session.get(DocumentUnitModel, unit.id)
        if model is None:
            model = DocumentUnitModel(
                id=unit.id,
                created_at=datetime_value(unit.created_at),
            )
            self.session.add(model)
        model.document_id = unit.document_id
        model.sequence_index = unit.sequence_index
        model.text_content = unit.text_content
        model.page_number = unit.page_number
        model.start_char = unit.start_char
        model.end_char = unit.end_char
        model.token_count = unit.token_count
        model.metadata_json = json_value(unit.metadata_json)
        model.raw_content_json = json_value(unit.raw_content_json)
        model.parser_name = unit.parser_name
        model.parser_version = unit.parser_version
        model.external_id = unit.external_id
        return unit

    def get_by_id(self, unit_id: str) -> DocumentUnit | None:
        model = self.session.get(DocumentUnitModel, unit_id)
        if model is None:
            return None
        return self._to_entity(model)

    def list_by_document(self, document_id: str) -> list[DocumentUnit]:
        """某份文档的全部内容单元，按 `sequence_index` **升序**。

        顺序由查询保证，而不是插入顺序 —— 界面里的页码顺序依赖这个契约。
        文档不存在时返回空列表（"文档不存在"的判定在 `DocumentQueryService`）。
        """
        models = (
            self.session.query(DocumentUnitModel)
            .filter(DocumentUnitModel.document_id == document_id)
            .order_by(DocumentUnitModel.sequence_index.asc())
            .all()
        )
        return [self._to_entity(model) for model in models]

    @staticmethod
    def _to_entity(model: DocumentUnitModel) -> DocumentUnit:
        return DocumentUnit(
            id=model.id,
            document_id=model.document_id,
            sequence_index=model.sequence_index,
            text_content=model.text_content,
            page_number=model.page_number,
            start_char=model.start_char,
            end_char=model.end_char,
            token_count=model.token_count,
            metadata_json=json_object(model.metadata_json),
            raw_content_json=json_object(model.raw_content_json),
            parser_name=model.parser_name,
            parser_version=model.parser_version,
            external_id=model.external_id,
            created_at=model.created_at,
        )
