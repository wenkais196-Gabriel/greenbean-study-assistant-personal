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
