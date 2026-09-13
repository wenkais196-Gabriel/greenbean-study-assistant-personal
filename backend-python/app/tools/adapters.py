"""
把生产对象适配成 Agent 工具所依赖的契约。

工具（`app/tools/*.py`）持有的是**长期对象**，而生产 repository 绑定单个 session、
生产 `Retriever` 的 `top_k` 在构造期固定 —— 这两处差距都在这里抹平：

- `ProductionChunkSearcher`：`ChunkSearchTool` 的 `search(query, workspace_id, top_k)` 协议；
- `SessionScoped*Repository`：让每次调用各自开一个 session，调用方不必管理 session 生命周期。

设计取舍与实测依据见 docs/specs/us-stage2-tools-wiring.md。
"""
from typing import Any

from app.config.settings import EMBEDDING_DIMENSION, RETRIEVAL_MAX_DISTANCE, RETRIEVAL_TOP_K
from app.db.orm import SessionFactory
from app.entities import AnalysisResult, DocumentRecord, Section
from app.rag.context_builder import ContextBuilder, ContextItem
from app.rag.retriever import Retriever
from app.repositories.analysis_result_repository import AnalysisResultRepository
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.document_unit_repository import DocumentUnitRepository
from app.repositories.embedding_repository import EmbeddingRepository
from app.repositories.section_repository import SectionRepository
from app.services.embedding_service import EmbeddingService


class ProductionChunkSearcher:
    """满足 `ChunkSearchTool` 检索协议（同步）的生产实现。"""

    def __init__(
        self,
        *,
        session_factory: SessionFactory,
        embedding_service: EmbeddingService | None = None,
        embedding_dimension: int = EMBEDDING_DIMENSION,
        max_distance: float | None = RETRIEVAL_MAX_DISTANCE,
    ) -> None:
        self.session_factory = session_factory
        self.embedding_service = embedding_service
        self.embedding_dimension = embedding_dimension
        self.max_distance = max_distance

    def search(
        self,
        *,
        query: str,
        workspace_id: str = "",
        top_k: int = RETRIEVAL_TOP_K,
    ) -> list[dict[str, Any]]:
        """按语义召回片段，返回可直接交给 Agent 的条目列表。

        - 空白 query 返回空列表，且**不加载模型**（沿用 `Retriever` 的既有行为）；
        - `workspace_id` 为空 = 不按 workspace 过滤，与生产问答链路一致；
        - 指定 workspace 时 `top_k` 就是"该 workspace 内的前 k 条"：生产查询用的
          **子查询**过滤是 pre-filter（sqlite-vec 实测，见规格 §4），**不需要过采样**。
        """
        if top_k <= 0:
            raise ValueError(f"top_k 必须为正整数，当前为 {top_k}")

        if not query.strip():
            return []

        with self.session_factory() as session:
            repository = EmbeddingRepository(
                session, embedding_dimension=self.embedding_dimension
            )
            hits = Retriever(
                self._get_embedding_service(),
                top_k=top_k,
                max_distance=self.max_distance,
            ).retrieve(repository, query, workspace_id=workspace_id.strip() or None)
            items = ContextBuilder(
                ChunkRepository(session),
                DocumentUnitRepository(session),
            ).build(hits)

        return [_to_dict(item) for item in items]

    def _get_embedding_service(self) -> EmbeddingService:
        """懒加载生产嵌入服务（构造时不加载模型权重，测试请注入假模型）。"""
        if self.embedding_service is None:
            self.embedding_service = EmbeddingService(dimension=self.embedding_dimension)
        return self.embedding_service


def _to_dict(item: ContextItem) -> dict[str, Any]:
    """上下文条目 → 工具返回值。字段与 `ContextItem` 一致，供引用回溯复用。"""
    return {
        "chunk_id": item.chunk_id,
        "text": item.text,
        "document_id": item.document_id,
        "page_number": item.page_number,
        "heading_path": item.heading_path,
        "distance": item.distance,
    }


class SessionScopedDocumentRepository:
    """每次调用各自开一个 session —— 工具持有的是长期对象，不能绑死单个 session。"""

    def __init__(self, session_factory: SessionFactory) -> None:
        self.session_factory = session_factory

    def get_by_id(self, document_id: str) -> DocumentRecord | None:
        with self.session_factory() as session:
            return DocumentRepository(session).get_by_id(document_id)


class SessionScopedSectionRepository:
    """同 `SessionScopedDocumentRepository`，面向小节。"""

    def __init__(self, session_factory: SessionFactory) -> None:
        self.session_factory = session_factory

    def get_by_id(self, section_id: str) -> Section | None:
        with self.session_factory() as session:
            return SectionRepository(session).get_by_id(section_id)


class SessionScopedAnalysisResultRepository:
    """同前，面向"按 workspace 查分析结果"（表里没有 workspace 列，靠关联过滤）。"""

    def __init__(self, session_factory: SessionFactory) -> None:
        self.session_factory = session_factory

    def get_by_workspace_id(self, workspace_id: str) -> list[AnalysisResult]:
        with self.session_factory() as session:
            return AnalysisResultRepository(session).get_by_workspace_id(workspace_id)
