"""
Agent 工具单元测试。

⚠️ 这里刻意用**符合生产签名的同步 Mock**（而不是 `AsyncMock`）当 repository：
生产 `DocumentRepository.get_by_id` / `SectionRepository.get_by_id` 都是同步方法，
用 AsyncMock 会让"await 一个同步方法"这种错误在测试里看不出来。
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.tools.analysis_result_tool import AnalysisResultTool
from app.tools.chunk_search_tool import ChunkSearchTool
from app.tools.document_retrieval_tool import DocumentRetrievalTool
from app.tools.quiz_generation_tool import QuizGenerationTool
from app.tools.section_context_tool import SectionContextTool
from app.tools.todo_generation_tool import TodoGenerationTool


class FakeSearcher:
    """符合 ChunkSearchTool 协议（同步实现）：search(query, workspace_id, top_k)。"""

    def __init__(self, results):
        self.results = results
        self.calls: list[dict] = []

    def search(self, *, query: str, workspace_id: str, top_k: int):
        self.calls.append({"query": query, "workspace_id": workspace_id, "top_k": top_k})
        return self.results[:top_k]


class AsyncFakeSearcher(FakeSearcher):
    """异步实现也应被支持（MCP / 远程检索器通常异步）。"""

    async def search(self, *, query: str, workspace_id: str, top_k: int):
        return super().search(query=query, workspace_id=workspace_id, top_k=top_k)


# --- ChunkSearchTool ---


@pytest.mark.us("US-STAGE1-TOOLS-01")
@pytest.mark.asyncio
async def test_chunk_search_tool_returns_hits_and_passes_top_k():
    searcher = FakeSearcher(
        [
            {"chunk_id": "c1", "content": "Algorithme de Dijkstra"},
            {"chunk_id": "c2", "content": "Parcours en largeur"},
        ]
    )
    tool = ChunkSearchTool(retriever=searcher)

    result = await tool.run(query="Dijkstra", workspace_id="ws1", top_k=1)

    assert result["success"] is True
    assert [hit["chunk_id"] for hit in result["data"]] == ["c1"]
    assert searcher.calls == [{"query": "Dijkstra", "workspace_id": "ws1", "top_k": 1}]


@pytest.mark.us("US-STAGE1-TOOLS-01")
@pytest.mark.asyncio
async def test_chunk_search_tool_supports_async_retriever():
    tool = ChunkSearchTool(retriever=AsyncFakeSearcher([{"chunk_id": "c1"}]))

    result = await tool.run(query="graphe", workspace_id="ws1")

    assert result["success"] is True
    assert result["data"] == [{"chunk_id": "c1"}]


@pytest.mark.us("US-STAGE1-TOOLS-01")
@pytest.mark.asyncio
async def test_chunk_search_tool_empty_query_validation():
    tool = ChunkSearchTool()

    with pytest.raises(ValueError, match="Query cannot be empty"):
        await tool.run(query="", workspace_id="ws1")


@pytest.mark.us("US-STAGE1-TOOLS-01")
@pytest.mark.asyncio
async def test_chunk_search_tool_unconfigured_retriever_reports_failure():
    """没配置依赖是**配置错误**，不能报 success —— 与其余工具保持一致。"""
    result = await ChunkSearchTool().run(query="valid")

    assert result["success"] is False
    assert "not configured" in result["error"]


# --- DocumentRetrievalTool ---


@pytest.mark.us("US-STAGE1-TOOLS-02")
@pytest.mark.asyncio
async def test_document_retrieval_tool_returns_document_details():
    repository = MagicMock()  # 同步 mock：与生产 DocumentRepository.get_by_id 一致
    document = MagicMock()
    document.id = "doc123"
    document.title = "Cours Algorithmique.pdf"
    document.file_type = "pdf"
    repository.get_by_id.return_value = document

    result = await DocumentRetrievalTool(document_repository=repository).run(document_id="doc123")

    assert result["success"] is True
    assert result["data"] == {
        "id": "doc123",
        "title": "Cours Algorithmique.pdf",
        "file_type": "pdf",
    }
    repository.get_by_id.assert_called_once_with("doc123")


@pytest.mark.us("US-STAGE1-TOOLS-02")
@pytest.mark.asyncio
async def test_document_retrieval_tool_not_found_and_unconfigured():
    repository = MagicMock()
    repository.get_by_id.return_value = None

    not_found = await DocumentRetrievalTool(document_repository=repository).run("missing")
    unconfigured = await DocumentRetrievalTool().run("doc123")

    assert not_found["success"] is False
    assert "not found" in not_found["error"]
    assert unconfigured["success"] is False
    assert "not configured" in unconfigured["error"]


@pytest.mark.us("US-STAGE1-TOOLS-02")
@pytest.mark.asyncio
async def test_document_retrieval_tool_empty_id_validation():
    with pytest.raises(ValueError, match="document_id cannot be empty"):
        await DocumentRetrievalTool().run(document_id="   ")


# --- SectionContextTool ---


@pytest.mark.us("US-STAGE1-TOOLS-03")
@pytest.mark.asyncio
async def test_section_context_tool_returns_section_title():
    repository = MagicMock()
    section = MagicMock()
    section.id = "sec-1"
    section.title = "Chapitre 1: Graphes"
    repository.get_by_id.return_value = section

    result = await SectionContextTool(section_repository=repository).run(section_id="sec-1")

    assert result["success"] is True
    assert result["data"] == {"id": "sec-1", "title": "Chapitre 1: Graphes"}


@pytest.mark.us("US-STAGE1-TOOLS-03")
@pytest.mark.asyncio
async def test_section_context_tool_empty_id_and_unconfigured():
    with pytest.raises(ValueError, match="section_id cannot be empty"):
        await SectionContextTool().run(section_id="")

    unconfigured = await SectionContextTool().run(section_id="sec-1")
    assert unconfigured["success"] is False
    assert "not configured" in unconfigured["error"]


# --- AnalysisResultTool ---


@pytest.mark.us("US-STAGE1-TOOLS-04")
@pytest.mark.asyncio
async def test_analysis_result_tool_formats_stored_summaries():
    repository = MagicMock()
    analysis = MagicMock()
    analysis.id = "ana-1"
    analysis.summary = "Résumé du chapitre"
    repository.get_by_workspace_id.return_value = [analysis]

    result = await AnalysisResultTool(analysis_repository=repository).run(workspace_id="ws-1")

    assert result["success"] is True
    assert result["data"] == [{"id": "ana-1", "summary": "Résumé du chapitre"}]


@pytest.mark.us("US-STAGE1-TOOLS-04")
@pytest.mark.asyncio
async def test_analysis_result_tool_empty_repository_results_and_validation():
    repository = MagicMock()
    repository.get_by_workspace_id.return_value = None

    empty = await AnalysisResultTool(analysis_repository=repository).run(workspace_id="ws-1")
    unconfigured = await AnalysisResultTool().run(workspace_id="ws-1")

    assert empty == {"success": True, "data": []}
    assert unconfigured["success"] is False
    with pytest.raises(ValueError, match="workspace_id cannot be empty"):
        await AnalysisResultTool().run(workspace_id="")


# --- QuizGenerationTool ---


def _provider_returning(content: str):
    provider = MagicMock()
    provider.chat_completion = AsyncMock(return_value=MagicMock(content=content))
    return provider


@pytest.mark.us("US-STAGE1-TOOLS-05")
@pytest.mark.asyncio
async def test_quiz_generation_tool_parses_provider_json():
    provider = _provider_returning(
        json.dumps({"quizzes": [{"question": "Qu'est-ce qu'un graphe?", "options": ["A", "B"], "answer": "A"}]})
    )

    result = await QuizGenerationTool(provider=provider).run(
        context_text="Les graphes...", num_questions=1
    )

    assert result["success"] is True
    assert result["data"]["quizzes"][0]["question"] == "Qu'est-ce qu'un graphe?"


@pytest.mark.us("US-STAGE1-TOOLS-05")
@pytest.mark.asyncio
async def test_quiz_generation_tool_handles_invalid_json_and_bad_arguments():
    provider = _provider_returning("```json\n{\"quizzes\": []}\n```")  # 带围栏 → 解析失败

    result = await QuizGenerationTool(provider=provider).run(context_text="texte")

    assert result["success"] is False
    assert "invalid JSON" in result["error"]
    with pytest.raises(ValueError, match="context_text cannot be empty"):
        await QuizGenerationTool(provider=provider).run(context_text="")
    with pytest.raises(ValueError, match="num_questions must be positive"):
        await QuizGenerationTool(provider=provider).run(context_text="texte", num_questions=0)
    unconfigured = await QuizGenerationTool().run(context_text="texte")
    assert unconfigured["success"] is False


# --- TodoGenerationTool ---


@pytest.mark.us("US-STAGE1-TOOLS-06")
@pytest.mark.asyncio
async def test_todo_generation_tool_uses_central_prompts_and_parses_json():
    provider = _provider_returning(
        json.dumps({"todos": [{"title": "Réviser les parcours", "priority": "high"}]})
    )

    result = await TodoGenerationTool(provider=provider).run(
        content_summary="Chapitre 2 sur les arbres", workspace_id="ws1"
    )

    assert result["success"] is True
    assert result["data"]["todos"][0]["priority"] == "high"

    messages = provider.chat_completion.call_args.kwargs["messages"]
    assert messages[0]["role"] == "system"
    assert "study todos" in messages[0]["content"]  # 来自 app/prompts/todo_prompts.py
    assert "Chapitre 2 sur les arbres" in messages[1]["content"]


@pytest.mark.us("US-STAGE1-TOOLS-06")
@pytest.mark.asyncio
async def test_todo_generation_tool_handles_invalid_json_and_validation():
    provider = _provider_returning("not json at all")

    result = await TodoGenerationTool(provider=provider).run(content_summary="texte")
    unconfigured = await TodoGenerationTool().run(content_summary="texte")

    assert result["success"] is False
    assert "invalid JSON" in result["error"]
    assert unconfigured["success"] is False
    with pytest.raises(ValueError, match="content_summary cannot be empty"):
        await TodoGenerationTool(provider=provider).run(content_summary="   ")


@pytest.mark.us("US-STAGE1-TOOLS-03")
@pytest.mark.asyncio
async def test_section_context_tool_reports_missing_section():
    """找不到小节时要报失败，而不是返回 success 与空数据。"""
    repository = MagicMock()
    repository.get_by_id.return_value = None

    result = await SectionContextTool(section_repository=repository).run(section_id="sec-x")

    assert result["success"] is False
    assert "not found" in result["error"]
