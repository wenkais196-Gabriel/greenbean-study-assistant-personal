"""
工具执行器：模型要调工具时，按名字找到装配好的工具并执行，把 dict 结果序列化成文本。

- 同步 / 异步 `run()` 都支持（工具契约允许两种实现，见 `app/tools/chunk_search_tool.py`）；
- 未知工具名是**明确的错误**（`UnknownToolError`）—— 上层 Agent 据此降级，不静默吞掉；
- 超长结果截断并加省略号，防止上下文被单个工具撑爆。
"""
import inspect
import json
from typing import Any, Mapping

from app.config.settings import TOOL_RESULT_MAX_CHARS
from app.providers.base import ToolCall


class UnknownToolError(KeyError):
    """模型请求了一个没有被装配的工具。"""


class ToolExecutor:
    def __init__(
        self,
        tools: Mapping[str, Any] | None = None,
        *,
        max_result_chars: int = TOOL_RESULT_MAX_CHARS,
    ) -> None:
        self._tools = dict(tools or {})
        self.max_result_chars = max_result_chars

    async def execute(self, tool_call: ToolCall) -> str:
        """执行一次工具调用，返回可回喂给模型的文本结果。"""
        tool = self._tools.get(tool_call.name)
        if tool is None:
            raise UnknownToolError(f"Unknown tool: {tool_call.name}")

        result = tool.run(**tool_call.arguments)
        if inspect.isawaitable(result):
            result = await result

        text = json.dumps(result, ensure_ascii=False, default=str)
        if len(text) > self.max_result_chars:
            text = text[: self.max_result_chars] + "…"
        return text
