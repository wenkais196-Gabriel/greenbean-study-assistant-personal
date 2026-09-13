from unittest.mock import AsyncMock, patch

import pytest

from app.providers.base import ChatResult, ToolCall
from app.providers.openai_compat_provider import OpenAICompatibleProvider


def _tool_call_mock(tool_call_id: str, name: str, arguments: str):
    tool_call = AsyncMock()
    tool_call.id = tool_call_id
    tool_call.function.name = name
    tool_call.function.arguments = arguments
    return tool_call


class TestOpenAICompatibleProvider:
    def test_initializes_with_config(self, provider_config_factory):
        provider = OpenAICompatibleProvider(provider_config_factory())
        assert provider.config.name == "test-cfg"

    @patch("app.providers.openai_compat_provider.AsyncOpenAI")
    @pytest.mark.asyncio
    async def test_chat_completion_returns_content(
        self, MockAsyncOpenAI, provider_config_factory
    ):
        mock_client = MockAsyncOpenAI.return_value
        mock_response = AsyncMock()
        mock_response.choices = [AsyncMock(message=AsyncMock(content="Hello"))]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        provider = OpenAICompatibleProvider(provider_config_factory())
        result = await provider.chat_completion(
            messages=[{"role": "user", "content": "hi"}]
        )
        assert isinstance(result, ChatResult)
        assert result.content == "Hello"

    @patch("app.providers.openai_compat_provider.AsyncOpenAI")
    @pytest.mark.asyncio
    async def test_chat_completion_passes_model_and_params(
        self, MockAsyncOpenAI, provider_config_factory
    ):
        mock_client = MockAsyncOpenAI.return_value
        mock_response = AsyncMock()
        mock_response.choices = [AsyncMock(message=AsyncMock(content="OK"))]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        provider = OpenAICompatibleProvider(provider_config_factory())
        await provider.chat_completion(
            messages=[{"role": "user", "content": "hi"}],
            model="override-model",
            temperature=0.5,
            max_tokens=100,
            response_format={"type": "json_object"},
        )
        kwargs = mock_client.chat.completions.create.call_args[1]
        assert kwargs["model"] == "override-model"
        assert kwargs["temperature"] == 0.5
        assert kwargs["max_tokens"] == 100
        assert kwargs["response_format"] == {"type": "json_object"}

    @patch("app.providers.openai_compat_provider.AsyncOpenAI")
    @pytest.mark.asyncio
    async def test_chat_completion_passes_tools_when_provided(
        self, MockAsyncOpenAI, provider_config_factory
    ):
        mock_client = MockAsyncOpenAI.return_value
        mock_response = AsyncMock()
        mock_response.choices = [AsyncMock(message=AsyncMock(content="OK"))]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        tools = [{"type": "function", "function": {"name": "chunk_search_tool", "parameters": {}}}]

        await OpenAICompatibleProvider(provider_config_factory()).chat_completion(
            messages=[{"role": "user", "content": "hi"}], tools=tools
        )

        assert mock_client.chat.completions.create.call_args[1]["tools"] == tools

    @patch("app.providers.openai_compat_provider.AsyncOpenAI")
    @pytest.mark.asyncio
    async def test_chat_completion_omits_tools_by_default(
        self, MockAsyncOpenAI, provider_config_factory
    ):
        mock_client = MockAsyncOpenAI.return_value
        mock_response = AsyncMock()
        mock_response.choices = [AsyncMock(message=AsyncMock(content="OK"))]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        await OpenAICompatibleProvider(provider_config_factory()).chat_completion(
            messages=[{"role": "user", "content": "hi"}]
        )

        assert "tools" not in mock_client.chat.completions.create.call_args[1]

    @patch("app.providers.openai_compat_provider.AsyncOpenAI")
    @pytest.mark.asyncio
    async def test_chat_completion_parses_tool_calls(
        self, MockAsyncOpenAI, provider_config_factory
    ):
        mock_client = MockAsyncOpenAI.return_value
        mock_response = AsyncMock()
        mock_response.choices = [
            AsyncMock(
                message=AsyncMock(
                    content="",
                    tool_calls=[_tool_call_mock("call-1", "chunk_search_tool", '{"query": "graphe"}')],
                )
            )
        ]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await OpenAICompatibleProvider(provider_config_factory()).chat_completion(
            messages=[{"role": "user", "content": "hi"}]
        )

        assert result.tool_calls == [
            ToolCall(id="call-1", name="chunk_search_tool", arguments={"query": "graphe"})
        ]

    @patch("app.providers.openai_compat_provider.AsyncOpenAI")
    @pytest.mark.asyncio
    async def test_chat_completion_tolerates_invalid_tool_call_arguments(
        self, MockAsyncOpenAI, provider_config_factory
    ):
        mock_client = MockAsyncOpenAI.return_value
        mock_response = AsyncMock()
        mock_response.choices = [
            AsyncMock(
                message=AsyncMock(
                    content="",
                    tool_calls=[_tool_call_mock("call-1", "chunk_search_tool", "not-json")],
                )
            )
        ]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await OpenAICompatibleProvider(provider_config_factory()).chat_completion(
            messages=[{"role": "user", "content": "hi"}]
        )

        assert result.tool_calls[0].arguments == {}

    @patch("app.providers.openai_compat_provider.AsyncOpenAI")
    @pytest.mark.asyncio
    async def test_chat_completion_without_tool_calls_yields_none(
        self, MockAsyncOpenAI, provider_config_factory
    ):
        mock_client = MockAsyncOpenAI.return_value
        mock_response = AsyncMock()
        message = AsyncMock(content="OK")
        message.tool_calls = None  # 真实 SDK：没要工具时该字段是 None
        mock_response.choices = [AsyncMock(message=message)]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await OpenAICompatibleProvider(provider_config_factory()).chat_completion(
            messages=[{"role": "user", "content": "hi"}]
        )

        assert result.tool_calls is None
