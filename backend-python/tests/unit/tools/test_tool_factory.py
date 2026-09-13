"""
工具生产装配入口（build_tools）的单元测试。

对应规格：docs/specs/us-stage2-tools-wiring.md

⚠️ 本文件只验证**接线**（谁被装进了谁），用 MagicMock 当 session_factory / embedding_service；
真实的检索与仓储读取行为由 tests/integration/tools/ 用真库覆盖。
"""
from unittest.mock import MagicMock

import pytest

from app.providers.registry import ProviderRegistry
from app.tools.adapters import (
    ProductionChunkSearcher,
    SessionScopedAnalysisResultRepository,
    SessionScopedDocumentRepository,
    SessionScopedSectionRepository,
)
from app.tools.analysis_result_tool import AnalysisResultTool
from app.tools.chunk_search_tool import ChunkSearchTool
from app.tools.document_retrieval_tool import DocumentRetrievalTool
from app.tools.factory import build_tools
from app.tools.quiz_generation_tool import QuizGenerationTool
from app.tools.section_context_tool import SectionContextTool
from app.tools.todo_generation_tool import TodoGenerationTool


@pytest.fixture
def isolated_provider_registry():
    """保存并恢复 ProviderRegistry 的类级状态 —— 装配入口会去读"当前激活的 provider"。"""
    previous_provider = ProviderRegistry._active_provider
    previous_config = ProviderRegistry._active_config
    ProviderRegistry.clear()
    yield
    ProviderRegistry._active_provider = previous_provider
    ProviderRegistry._active_config = previous_config


@pytest.fixture
def wired_tools():
    return build_tools(
        session_factory=MagicMock(),
        embedding_service=MagicMock(),
        provider=MagicMock(),
    )


@pytest.mark.us("US-STAGE2-TOOLS-01")
def test_build_tools_returns_all_six_tools(wired_tools):
    assert isinstance(wired_tools.chunk_search, ChunkSearchTool)
    assert isinstance(wired_tools.document_retrieval, DocumentRetrievalTool)
    assert isinstance(wired_tools.section_context, SectionContextTool)
    assert isinstance(wired_tools.analysis_result, AnalysisResultTool)
    assert isinstance(wired_tools.quiz_generation, QuizGenerationTool)
    assert isinstance(wired_tools.todo_generation, TodoGenerationTool)


@pytest.mark.us("US-STAGE2-TOOLS-01")
def test_build_tools_wires_production_adapters(wired_tools):
    """工具的依赖契约要求"持有 repository"，而生产 repository 绑定单个 session → 一律走适配器。"""
    assert isinstance(wired_tools.chunk_search.retriever, ProductionChunkSearcher)
    assert isinstance(
        wired_tools.document_retrieval.document_repository, SessionScopedDocumentRepository
    )
    assert isinstance(
        wired_tools.section_context.section_repository, SessionScopedSectionRepository
    )
    assert isinstance(
        wired_tools.analysis_result.analysis_repository, SessionScopedAnalysisResultRepository
    )


@pytest.mark.us("US-STAGE2-TOOLS-01")
def test_build_tools_hands_the_same_session_factory_to_every_stateful_tool(wired_tools):
    session_factory = MagicMock()
    tools = build_tools(session_factory=session_factory, embedding_service=MagicMock())

    assert tools.chunk_search.retriever.session_factory is session_factory
    assert tools.document_retrieval.document_repository.session_factory is session_factory
    assert tools.section_context.section_repository.session_factory is session_factory
    assert tools.analysis_result.analysis_repository.session_factory is session_factory


@pytest.mark.us("US-STAGE2-TOOLS-01")
def test_build_tools_passes_provider_to_generation_tools():
    provider = MagicMock()

    tools = build_tools(
        session_factory=MagicMock(), embedding_service=MagicMock(), provider=provider
    )

    assert tools.quiz_generation.provider is provider
    assert tools.todo_generation.provider is provider


@pytest.mark.us("US-STAGE2-TOOLS-01")
def test_build_tools_uses_the_active_provider_by_default(isolated_provider_registry):
    active = MagicMock()
    ProviderRegistry._active_provider = active

    tools = build_tools(session_factory=MagicMock(), embedding_service=MagicMock())

    assert tools.quiz_generation.provider is active


@pytest.mark.us("US-STAGE2-TOOLS-01")
def test_build_tools_without_active_provider_leaves_generation_tools_unconfigured(
    isolated_provider_registry,
):
    """没有激活的 provider 时装配不该炸 —— 生成类工具会在被调用时报 not configured。"""
    tools = build_tools(session_factory=MagicMock(), embedding_service=MagicMock())

    assert tools.quiz_generation.provider is None
    assert tools.todo_generation.provider is None
