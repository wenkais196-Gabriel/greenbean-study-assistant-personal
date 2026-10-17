"""
界面只读查询：文档列表与某份文档的内容单元。

与 `DocumentIngestService`（写侧）分开 —— 这里只有读，没有事务边界上的副作用，
也不需要 trace / 进度回调。

工作区过滤（R1-2 起）：`list_documents(workspace_id=...)` 把过滤**下推到 SQL**；
不传（`None`）保持"全部"语义。空串不是合法的过滤值 —— 空串意味着"没有值"，
必须由调用方（控制器）先把它收敛成 `None`，否则会静默返回空列表。
"""
from app.db.orm import SessionFactory
from app.entities import DocumentRecord, DocumentUnit
from app.repositories.document_repository import DocumentRepository
from app.repositories.document_unit_repository import DocumentUnitRepository


class DocumentQueryService:
    def __init__(self, session_factory: SessionFactory) -> None:
        self.session_factory = session_factory

    def list_documents(self, workspace_id: str | None = None) -> list[DocumentRecord]:
        """文档列表，按上传时间倒序（新的在前）。

        :param workspace_id: 只看该工作区；`None`（默认）= 全部。
            "传空串"与"不传"在语义上是同一件事（没有过滤条件），收敛由控制器负责 ——
            服务层不做猜测，但也不会把空串当成一个真实的工作区去筛。
        """
        with self.session_factory() as session:
            return DocumentRepository(session).list_all(workspace_id=workspace_id)

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
