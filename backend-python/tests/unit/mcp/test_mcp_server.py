"""
MCP server 的离线单元测试。

对应规格：docs/specs/us-stage2-mcp-server.md（本批实现后补写）

不真起 stdio 进程：直接调用 `MCPServer.list_tools()` / `MCPServer.call_tool()`，
等价于客户端经 JSON-RPC 做的事，但完全离线、可重复。
"""
import pytest

from app.mcp_server import build_server
from app.tools.factory import ToolSet


class FakeTool:
    """按预设结果返回的工具替身，记录收到的参数。"""

    def __init__(self, description: str, result=None, error=None):
        self.description = description
        self.result = result if result is not None else {"success": True, "data": []}
        self.error = error
        self.calls: list[dict] = []

    async def run(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.result


def _fake_toolset() -> ToolSet:
    return ToolSet(
        chunk_search=FakeTool("search chunks"),
        document_retrieval=FakeTool("get document"),
        section_context=FakeTool("get section"),
        analysis_result=FakeTool("list analyses"),
        quiz_generation=FakeTool("make quiz"),
        todo_generation=FakeTool("make todos"),
    )


ALL_TOOL_NAMES = [
    "chunk_search_tool",
    "document_retrieval_tool",
    "section_context_tool",
    "analysis_result_tool",
    "quiz_generation_tool",
    "todo_generation_tool",
]

CALLABLE_TOOLS = [
    ("chunk_search_tool", {"query": "graphe"}),
    ("document_retrieval_tool", {"document_id": "doc-1"}),
    ("section_context_tool", {"section_id": "sec-1"}),
    ("analysis_result_tool", {"workspace_id": "ws-1"}),
    ("quiz_generation_tool", {"context_text": "les graphes"}),
    ("todo_generation_tool", {"content_summary": "chapitre 2"}),
]


@pytest.mark.us("US-STAGE2-MCP-01")
@pytest.mark.asyncio
async def test_build_server_lists_all_six_tools():
    server = build_server(toolset=_fake_toolset())

    tools = await server.list_tools()

    assert [tool.name for tool in tools] == ALL_TOOL_NAMES
    assert tools[0].description == "search chunks"


@pytest.mark.us("US-STAGE2-MCP-01")
@pytest.mark.asyncio
async def test_chunk_search_tool_forwards_arguments_and_serializes_result():
    toolset = _fake_toolset()
    toolset.chunk_search.result = {"success": True, "data": [{"chunk_id": "c1"}]}
    server = build_server(toolset=toolset)

    result = await server.call_tool(
        "chunk_search_tool",
        {"query": "graphe", "workspace_id": "ws-1", "top_k": 3},
    )

    text = result.content[0].text
    assert '"success": true' in text
    assert '"chunk_id": "c1"' in text
    assert toolset.chunk_search.calls == [
        {"query": "graphe", "workspace_id": "ws-1", "top_k": 3}
    ]


@pytest.mark.us("US-STAGE2-MCP-01")
@pytest.mark.asyncio
async def test_tool_exception_becomes_failure_json_not_transport_error():
    toolset = _fake_toolset()
    toolset.chunk_search.error = RuntimeError("boom")
    server = build_server(toolset=toolset)

    result = await server.call_tool("chunk_search_tool", {"query": "x"})

    text = result.content[0].text
    assert '"success": false' in text
    assert "RuntimeError" in text


@pytest.mark.us("US-STAGE2-MCP-01")
@pytest.mark.asyncio
@pytest.mark.parametrize("tool_name,arguments", CALLABLE_TOOLS)
async def test_every_tool_is_callable_and_returns_success_json(tool_name, arguments):
    server = build_server(toolset=_fake_toolset())

    result = await server.call_tool(tool_name, arguments)

    assert '"success": true' in result.content[0].text


@pytest.mark.us("US-STAGE2-MCP-01")
@pytest.mark.asyncio
async def test_chunk_search_input_schema_marks_query_required():
    server = build_server(toolset=_fake_toolset())

    tools = await server.list_tools()
    chunk = next(tool for tool in tools if tool.name == "chunk_search_tool")

    assert chunk.input_schema["required"] == ["query"]
    assert set(chunk.input_schema["properties"]) == {"query", "workspace_id", "top_k"}


@pytest.mark.us("US-STAGE2-MCP-01")
@pytest.mark.asyncio
async def test_build_server_without_toolset_uses_production_assembly():
    """生产装配分支：构造时不碰磁盘、不加载模型（嵌入服务与数据库都是懒的）。"""
    from app.providers.registry import ProviderRegistry

    ProviderRegistry.clear()
    server = build_server()

    tools = await server.list_tools()

    assert [tool.name for tool in tools] == ALL_TOOL_NAMES
