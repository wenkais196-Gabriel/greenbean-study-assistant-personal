"""
Agent 工具的生产装配入口。

把生产对象（数据库会话、本地嵌入、当前激活的 provider）接进 `app/tools/` 的六个工具，
让编排层不必自己拼装依赖。设计与"为什么需要适配层"见 docs/specs/us-stage2-tools-wiring.md。
"""
from dataclasses import dataclass

from app.db.orm import SessionFactory
from app.db.runtime import lazy_session_factory
from app.providers.base import AIProvider
from app.providers.registry import ProviderNotFoundError, ProviderRegistry
from app.services.embedding_service import EmbeddingService
from app.config.settings import EMBEDDING_DIMENSION
from app.tools.adapters import (
    ProductionChunkSearcher,
    SessionScopedAnalysisResultRepository,
    SessionScopedDocumentRepository,
    SessionScopedSectionRepository,
)
from app.tools.analysis_result_tool import AnalysisResultTool
from app.tools.chunk_search_tool import ChunkSearchTool
from app.tools.document_retrieval_tool import DocumentRetrievalTool
from app.tools.quiz_generation_tool import QuizGenerationTool
from app.tools.section_context_tool import SectionContextTool
from app.tools.todo_generation_tool import TodoGenerationTool


@dataclass(frozen=True)
class ToolSet:
    """一次装配产出的全部工具。"""

    chunk_search: ChunkSearchTool
    document_retrieval: DocumentRetrievalTool
    section_context: SectionContextTool
    analysis_result: AnalysisResultTool
    quiz_generation: QuizGenerationTool
    todo_generation: TodoGenerationTool


def build_tools(
    *,
    session_factory: SessionFactory | None = None,
    embedding_service: EmbeddingService | None = None,
    provider: AIProvider | None = None,
    embedding_dimension: int = EMBEDDING_DIMENSION,
) -> ToolSet:
    """装配六个工具。

    :param session_factory: 会话工厂；默认用生产的懒加载工厂（**构造时不碰磁盘**）
    :param embedding_service: 嵌入服务；默认由检索适配器懒加载（测试请注入假模型）
    :param provider: 生成类工具用的 provider；默认取当前激活的那个。没有激活的 provider
        时留空 —— 装配不该因此失败，工具被调用时会报 `not configured`
    :param embedding_dimension: 检索适配器用的向量维度；**必须与建库时一致**
        （测试库是 8 维，生产是 settings 里的 1024 维）
    """
    session_factory = session_factory or lazy_session_factory()
    provider = provider or _active_provider_or_none()

    return ToolSet(
        chunk_search=ChunkSearchTool(
            retriever=ProductionChunkSearcher(
                session_factory=session_factory,
                embedding_service=embedding_service,
                embedding_dimension=embedding_dimension,
            )
        ),
        document_retrieval=DocumentRetrievalTool(
            document_repository=SessionScopedDocumentRepository(session_factory)
        ),
        section_context=SectionContextTool(
            section_repository=SessionScopedSectionRepository(session_factory)
        ),
        analysis_result=AnalysisResultTool(
            analysis_repository=SessionScopedAnalysisResultRepository(session_factory)
        ),
        quiz_generation=QuizGenerationTool(provider=provider),
        todo_generation=TodoGenerationTool(provider=provider),
    )


def _active_provider_or_none() -> AIProvider | None:
    """当前激活的 provider；没有激活时返回 None（装配不该因此失败）。"""
    try:
        return ProviderRegistry.get_active()
    except ProviderNotFoundError:
        return None
