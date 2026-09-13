"""
Agent 工具执行器的单元测试。

对应规格：docs/specs/us-stage2-agent-tool-loop.md（本批实现后补写）

工具执行器是"模型要调工具"与"生产工具"之间的那层壳：
- 按名字找到工具、执行（同步/异步都行）、把 dict 结果序列化成喂给模型的文本；
- 未知工具名是明确的错误（交给上层降级），不静默吞掉。
"""
from unittest.mock import AsyncMock

import pytest

from app.agents.tool_executor import ToolExecutor, UnknownToolError
from app.providers.base import ToolCall


class FakeTool:
    def __init__(self, result, error=None):
        self.result = result
        self.error = error
        self.calls: list[dict] = []

    async def run(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.result


class SyncFakeTool(FakeTool):
    """同步实现也要被支持 —— 工具契约允许同步或异步 run()。"""

    def run(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.result


@pytest.mark.us("US-STAGE2-TOOL-LOOP-01")
@pytest.mark.asyncio
async def test_executor_runs_async_tool_and_serializes_result():
    tool = FakeTool({"success": True, "data": [{"chunk_id": "c1"}]})
    executor = ToolExecutor({"chunk_search_tool": tool})

    text = await executor.execute(
        ToolCall(id="call-1", name="chunk_search_tool", arguments={"query": "graphe"})
    )

    assert tool.calls == [{"query": "graphe"}]
    assert '"success": true' in text
    assert '"chunk_id": "c1"' in text


@pytest.mark.us("US-STAGE2-TOOL-LOOP-01")
@pytest.mark.asyncio
async def test_executor_supports_sync_tool():
    tool = SyncFakeTool({"success": True, "data": []})

    text = await ToolExecutor({"t": tool}).execute(ToolCall(id="c", name="t", arguments={}))

    assert text == '{"success": true, "data": []}'


@pytest.mark.us("US-STAGE2-TOOL-LOOP-01")
@pytest.mark.asyncio
async def test_executor_rejects_unknown_tool():
    executor = ToolExecutor({"known": AsyncMock()})

    with pytest.raises(UnknownToolError, match="no_such"):
        await executor.execute(ToolCall(id="c", name="no_such", arguments={}))


@pytest.mark.us("US-STAGE2-TOOL-LOOP-01")
@pytest.mark.asyncio
async def test_executor_truncates_oversized_results():
    """超长结果要截断，防止把上下文撑爆；截断后加省略号标记。"""
    tool = FakeTool({"data": "x" * 100})
    executor = ToolExecutor({"t": tool}, max_result_chars=10)

    text = await executor.execute(ToolCall(id="c", name="t", arguments={}))

    assert len(text) == 11  # 10 字符 + 省略号
    assert text.endswith("…")
