"""
Unit tests for ChatAgent with high-fidelity US-to-Test transformation:
- Explicit US traceability tags (@pytest.mark.us)
- Structured Gherkin (Given-When-Then) Acceptance Criteria specifications
- Complete Trio coverage: Happy Path, Edge Cases, and Failure Paths
"""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.agents.chat_agent import ChatAgent
from app.providers.base import ChatResult
from app.schemas.chat_schema import ChatRequest, ChatResponse


@pytest.mark.us("US-STAGE1-AGENT-CHAT-01")
@pytest.mark.asyncio
@patch("app.agents.chat_agent.ProviderRegistry")
@patch("app.agents.classification_agent.ProviderRegistry")
async def test_chat_agent_generate_response_success(MockClassifyRegistry, MockChatRegistry):
    """
    [AC-CHAT-01.1] Happy Path: Generate bilingual study response for concept question.

    Given: ChatAgent with active Classification and Chat providers returning valid intent & response
    When: generate_response() is called with French user query "Explique-moi le mock"
    Then: Should route to CONCEPT, return ChatResponse with bilingual explanation, and verify Provider call
    """
    mock_router_provider = MagicMock()
    mock_router_provider.chat_completion = AsyncMock(
        return_value=ChatResult(content='{"route": "CONCEPT", "reason": "concept question"}')
    )
    MockClassifyRegistry.get_active.return_value = mock_router_provider

    mock_chat_provider = MagicMock()
    mock_chat_provider.chat_completion = AsyncMock(
        return_value=ChatResult(
            content="中法双语回复：这是一个Mock测试。\nExplication : C'est un test mock."
        )
    )
    MockChatRegistry.get_active.return_value = mock_chat_provider

    agent = ChatAgent()
    request = ChatRequest(
        session_id="test-session-1",
        query="Explique-moi le mock",
        history=[{"role": "user", "content": "Bonjour"}],
    )

    response = await agent.generate_response(request)

    assert isinstance(response, ChatResponse)
    assert response.session_id == "test-session-1"
    assert "这是一个Mock测试。" in response.answer
    assert response.source_context is None
    mock_chat_provider.chat_completion.assert_called_once()


@pytest.mark.us("US-STAGE1-AGENT-CHAT-01")
@pytest.mark.asyncio
@patch("app.agents.chat_agent.ProviderRegistry")
@patch("app.agents.classification_agent.ProviderRegistry")
async def test_chat_agent_classification_failure_fallback(MockClassifyRegistry, MockChatRegistry):
    """
    [AC-CHAT-01.2] Failure Path: Graceful fallback when intent classifier returns invalid JSON.

    Given: Classification provider returns malformed non-JSON string "INVALID_JSON_RESPONSE"
    When: generate_response() is called
    Then: Agent should gracefully catch parsing failure, fall back to DEFAULT route, and return response without crashing
    """
    mock_router_provider = MagicMock()
    mock_router_provider.chat_completion = AsyncMock(
        return_value=ChatResult(content="INVALID_JSON_RESPONSE")
    )
    MockClassifyRegistry.get_active.return_value = mock_router_provider

    mock_chat_provider = MagicMock()
    mock_chat_provider.chat_completion = AsyncMock(
        return_value=ChatResult(content="Fallback answer")
    )
    MockChatRegistry.get_active.return_value = mock_chat_provider

    agent = ChatAgent()
    request = ChatRequest(
        session_id="test-session-fallback",
        query="Random query",
        history=[],
    )

    response = await agent.generate_response(request)

    assert response.session_id == "test-session-fallback"
    assert response.answer == "Fallback answer"


@pytest.mark.us("US-STAGE1-AGENT-CHAT-01")
@pytest.mark.asyncio
@patch("app.agents.chat_agent.ProviderRegistry")
@patch("app.agents.classification_agent.ProviderRegistry")
async def test_chat_agent_provider_error_handling(MockClassifyRegistry, MockChatRegistry):
    """
    [AC-CHAT-01.3] Failure Path: Transparent exception propagation when LLM Provider API fails.

    Given: Chat provider API throws RuntimeError timeout error
    When: generate_response() is invoked
    Then: Should raise RuntimeError with transparent error message
    """
    mock_router_provider = MagicMock()
    mock_router_provider.chat_completion = AsyncMock(
        return_value=ChatResult(content='{"route": "CONCEPT", "reason": "test"}')
    )
    MockClassifyRegistry.get_active.return_value = mock_router_provider

    mock_chat_provider = MagicMock()
    mock_chat_provider.chat_completion = AsyncMock(
        side_effect=RuntimeError("Provider API timeout")
    )
    MockChatRegistry.get_active.return_value = mock_chat_provider

    agent = ChatAgent()
    request = ChatRequest(
        session_id="test-session-err",
        query="Error test",
    )

    with pytest.raises(RuntimeError) as exc_info:
        await agent.generate_response(request)

    assert "Provider API timeout" in str(exc_info.value)


@pytest.mark.us("US-STAGE1-AGENT-CHAT-01")
@pytest.mark.asyncio
@patch("app.agents.chat_agent.ProviderRegistry")
@patch("app.agents.classification_agent.ProviderRegistry")
async def test_generate_response_uses_passed_context_and_returns_sources(
    MockClassifyRegistry, MockChatRegistry
):
    """AC-CHAT-01.4：调用方传入的检索上下文必须进 prompt，来源必须原样带回。

    这样 ChatAgent 就不需要自己检索（分层：检索归 ChatService）。
    """
    mock_router_provider = MagicMock()
    mock_router_provider.chat_completion = AsyncMock(
        return_value=ChatResult(content='{"route": "CONCEPT", "reason": "test"}')
    )
    MockClassifyRegistry.get_active.return_value = mock_router_provider

    mock_chat_provider = MagicMock()
    mock_chat_provider.chat_completion = AsyncMock(
        return_value=ChatResult(content="答案 [来源 1]")
    )
    MockChatRegistry.get_active.return_value = mock_chat_provider

    sources = [{"chunk_id": "c1", "document_id": "doc-1", "page_number": 3}]
    agent = ChatAgent()
    request = ChatRequest(session_id="s-ctx", query="监督学习是什么？")

    response = await agent.generate_response(
        request,
        context="[来源 1]\nLe polymorphisme...",
        sources=sources,
    )

    prompt = mock_chat_provider.chat_completion.call_args.kwargs["messages"][-1]["content"]
    assert "Le polymorphisme" in prompt
    assert "监督学习是什么？" in prompt
    assert response.source_context == sources


# ===== 阶段 2：Agent 工具调用循环（US-STAGE2-TOOL-LOOP）=====
# 本节 import 就近放在这里，避免改动文件顶部的既有 import 区块。
import asyncio  # noqa: E402
from contextlib import contextmanager  # noqa: E402

from app.agents.tool_executor import ToolExecutor  # noqa: E402
from app.providers.base import ToolCall  # noqa: E402

_ROUTE_JSON = '{"route": "CONCEPT", "reason": "tool loop"}'
_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "chunk_search_tool",
            "description": "Searches chunks.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    }
]


class LoopFakeTool:
    """按预设结果返回的工具替身：可注入异常与延迟（测超时降级）。"""

    def __init__(self, result=None, error=None, delay=0.0):
        self.result = result if result is not None else {"success": True, "data": [{"chunk_id": "c1"}]}
        self.error = error
        self.delay = delay
        self.calls: list[dict] = []

    async def run(self, **kwargs):
        self.calls.append(kwargs)
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error is not None:
            raise self.error
        return self.result


@contextmanager
def _patched_loop_providers(chat_side_effect):
    """把路由与回答两个 Registry 都换成假 provider；产出回答 provider 供断言。"""
    with patch("app.agents.classification_agent.ProviderRegistry") as router_registry, patch(
        "app.agents.chat_agent.ProviderRegistry"
    ) as chat_registry:
        router_provider = MagicMock()
        router_provider.chat_completion = AsyncMock(return_value=ChatResult(content=_ROUTE_JSON))
        router_registry.get_active.return_value = router_provider

        chat_provider = MagicMock()
        chat_provider.chat_completion = AsyncMock(side_effect=chat_side_effect)
        chat_registry.get_active.return_value = chat_provider
        yield chat_provider


def _loop_request(query: str = "什么是图？") -> ChatRequest:
    return ChatRequest(session_id="s-loop", query=query)


@pytest.mark.us("US-STAGE2-TOOL-LOOP-01")
@pytest.mark.asyncio
async def test_generate_response_executes_tool_and_feeds_result_back():
    """模型第一轮要工具、第二轮给出答案 —— 循环执行工具并把结果回喂，答案取最后一轮。"""
    recorder = MagicMock()
    with _patched_loop_providers(
        [
            ChatResult(
                content="",
                tool_calls=[
                    ToolCall(id="call-1", name="chunk_search_tool", arguments={"query": "graphe"})
                ],
            ),
            ChatResult(content="Le graphe est ...", input_tokens=11, output_tokens=22),
        ]
    ) as chat_provider:
        tool = LoopFakeTool()
        agent = ChatAgent(trace_recorder=recorder)

        response = await agent.generate_response(
            _loop_request(),
            context="[来源 1]\ncontexte initial",
            sources=[{"chunk_id": "c0"}],
            tool_schemas=_TOOL_SCHEMAS,
            tool_executor=ToolExecutor({"chunk_search_tool": tool}),
        )

    assert response.answer == "Le graphe est ..."
    assert response.usage.input_tokens == 11
    assert tool.calls == [{"query": "graphe"}]

    calls = chat_provider.chat_completion.call_args_list
    assert len(calls) == 2
    assert calls[0].kwargs["tools"] == _TOOL_SCHEMAS
    second_messages = calls[1].kwargs["messages"]
    tool_messages = [m for m in second_messages if m.get("role") == "tool"]
    assert [m["tool_call_id"] for m in tool_messages] == ["call-1"]
    assert '"success"' in tool_messages[0]["content"]

    tool_spans = [
        c
        for c in recorder.record_span.call_args_list
        if c.kwargs.get("span_name") == "greenbean.tool.call"
    ]
    assert tool_spans
    assert tool_spans[0].kwargs["attributes"]["greenbean.tool.name"] == "chunk_search_tool"


@pytest.mark.us("US-STAGE2-TOOL-LOOP-01")
@pytest.mark.asyncio
async def test_tool_failure_falls_back_to_plain_answer():
    """工具执行失败 → 停止循环、用已有上下文直答（不带 tools），异常不出给调用方。"""
    recorder = MagicMock()
    with _patched_loop_providers(
        [
            ChatResult(
                content="",
                tool_calls=[
                    ToolCall(id="call-1", name="chunk_search_tool", arguments={"query": "graphe"})
                ],
            ),
            ChatResult(content="降级直答"),
        ]
    ) as chat_provider:
        tool = LoopFakeTool(error=RuntimeError("boom"))
        agent = ChatAgent(trace_recorder=recorder)

        response = await agent.generate_response(
            _loop_request(),
            tool_schemas=_TOOL_SCHEMAS,
            tool_executor=ToolExecutor({"chunk_search_tool": tool}),
        )

    assert response.answer == "降级直答"
    calls = chat_provider.chat_completion.call_args_list
    assert len(calls) == 2
    assert "tools" not in calls[1].kwargs, "降级那次调用不能再带 tools"

    error_spans = [
        c
        for c in recorder.record_span.call_args_list
        if c.kwargs.get("span_name") == "greenbean.tool.call" and c.kwargs.get("error")
    ]
    assert error_spans
    assert "RuntimeError" in error_spans[0].kwargs["error"]


@pytest.mark.us("US-STAGE2-TOOL-LOOP-01")
@pytest.mark.asyncio
async def test_rounds_exhausted_forces_plain_answer():
    """模型连续要工具直到轮数上限 → 强制直答（不无限循环）。"""
    with _patched_loop_providers(
        [
            ChatResult(
                content="",
                tool_calls=[
                    ToolCall(id="c1", name="chunk_search_tool", arguments={"query": "graphe"})
                ],
            ),
            ChatResult(
                content="",
                tool_calls=[
                    ToolCall(id="c2", name="chunk_search_tool", arguments={"query": "graphe"})
                ],
            ),
            ChatResult(content="强制直答"),
        ]
    ) as chat_provider:
        agent = ChatAgent(max_tool_rounds=2)

        response = await agent.generate_response(
            _loop_request(),
            tool_schemas=_TOOL_SCHEMAS,
            tool_executor=ToolExecutor({"chunk_search_tool": LoopFakeTool()}),
        )

    assert response.answer == "强制直答"
    assert chat_provider.chat_completion.call_count == 3


@pytest.mark.us("US-STAGE2-TOOL-LOOP-01")
@pytest.mark.asyncio
async def test_unknown_tool_name_falls_back():
    """模型要一个不存在的工具 → 当作执行失败降级。"""
    with _patched_loop_providers(
        [
            ChatResult(
                content="",
                tool_calls=[ToolCall(id="c1", name="no_such_tool", arguments={})],
            ),
            ChatResult(content="降级直答"),
        ]
    ) as chat_provider:
        response = await ChatAgent().generate_response(
            _loop_request(),
            tool_schemas=_TOOL_SCHEMAS,
            tool_executor=ToolExecutor({"chunk_search_tool": LoopFakeTool()}),
        )

    assert response.answer == "降级直答"
    assert chat_provider.chat_completion.call_count == 2


@pytest.mark.us("US-STAGE2-TOOL-LOOP-01")
@pytest.mark.asyncio
async def test_tool_timeout_falls_back():
    """工具超时 → 当作执行失败降级（asyncio.timeout 兜底）。"""
    with _patched_loop_providers(
        [
            ChatResult(
                content="",
                tool_calls=[
                    ToolCall(id="c1", name="chunk_search_tool", arguments={"query": "graphe"})
                ],
            ),
            ChatResult(content="超时降级直答"),
        ]
    ) as chat_provider:
        agent = ChatAgent(tool_timeout_seconds=0.001)

        response = await agent.generate_response(
            _loop_request(),
            tool_schemas=_TOOL_SCHEMAS,
            tool_executor=ToolExecutor({"chunk_search_tool": LoopFakeTool(delay=0.05)}),
        )

    assert response.answer == "超时降级直答"
    assert chat_provider.chat_completion.call_count == 2
