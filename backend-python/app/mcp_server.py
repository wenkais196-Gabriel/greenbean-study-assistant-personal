"""
把 app/tools/ 的六个工具按 MCP 协议暴露（stdio 传输）。

本地 MCP server 的标准形态：`python backend-python/scripts/run_mcp_server.py` 起一个 stdio 进程，
Claude Desktop / Cursor 之类的 MCP 客户端通过 JSON-RPC 与之通信。

MCP 层只做协议翻译：工具与生产装配复用 `build_tools()`，业务逻辑不在这里。
"""
import json
from typing import Any

from mcp.server.mcpserver import MCPServer

from app.tools.factory import ToolSet, build_tools

SERVER_NAME = "greenbean-study-assistant"
SERVER_VERSION = "0.1.0"

_SERVER_DESCRIPTION = (
    "Tools of a local course-material QA assistant for Chinese-speaking students in France: "
    "retrieval, documents, sections, previous analyses, quizzes and study todos."
)


def build_server(toolset: ToolSet | None = None) -> MCPServer:
    """构造 MCP server。

    :param toolset: 六个工具的装配结果；`None` 时走生产装配（构造时不碰磁盘、不加载模型，
        检索的嵌入服务与数据库都是懒加载）
    """
    server = MCPServer(
        name=SERVER_NAME,
        title="GreenBean Study Assistant tools",
        description=_SERVER_DESCRIPTION,
        version=SERVER_VERSION,
    )
    _register_tools(server, toolset or build_tools())
    return server


def _register_tools(server: MCPServer, toolset: ToolSet) -> None:
    """把六个工具逐个包成 MCP 工具。参数与工具 `run()` 签名一一对应。"""

    @server.tool(name="chunk_search_tool", description=toolset.chunk_search.description)
    async def chunk_search_tool(query: str, workspace_id: str = "", top_k: int = 5) -> str:
        return await _run(
            toolset.chunk_search, query=query, workspace_id=workspace_id, top_k=top_k
        )

    @server.tool(
        name="document_retrieval_tool", description=toolset.document_retrieval.description
    )
    async def document_retrieval_tool(document_id: str) -> str:
        return await _run(toolset.document_retrieval, document_id=document_id)

    @server.tool(name="section_context_tool", description=toolset.section_context.description)
    async def section_context_tool(section_id: str) -> str:
        return await _run(toolset.section_context, section_id=section_id)

    @server.tool(name="analysis_result_tool", description=toolset.analysis_result.description)
    async def analysis_result_tool(workspace_id: str) -> str:
        return await _run(toolset.analysis_result, workspace_id=workspace_id)

    @server.tool(name="quiz_generation_tool", description=toolset.quiz_generation.description)
    async def quiz_generation_tool(context_text: str, num_questions: int = 3) -> str:
        return await _run(
            toolset.quiz_generation, context_text=context_text, num_questions=num_questions
        )

    @server.tool(name="todo_generation_tool", description=toolset.todo_generation.description)
    async def todo_generation_tool(content_summary: str, workspace_id: str = "") -> str:
        return await _run(
            toolset.todo_generation, content_summary=content_summary, workspace_id=workspace_id
        )


async def _run(tool: Any, **kwargs: Any) -> str:
    """执行一次工具调用，把 dict 结果（或异常）序列化成 JSON 文本。

    ⚠️ 异常要在这里拦住：mcp 2.x 会把工具异常抛成 `UnexpectedToolError`，
    那对 MCP 客户端是传输层错误；包成 `{"success": false, ...}` 才是可读结果。
    """
    try:
        result = await tool.run(**kwargs)
    except Exception as exc:
        result = {"success": False, "error": f"{type(exc).__name__}: {exc}"}
    return json.dumps(result, ensure_ascii=False, default=str)
