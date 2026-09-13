import json

from openai import AsyncOpenAI

from app.entities.provider_config import ProviderConfig
from app.providers.base import AIProvider, ChatResult, ToolCall


class OpenAICompatibleProvider(AIProvider):
    def __init__(self, config: ProviderConfig) -> None:
        self.config = config
        self._client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.api_host.rstrip("/"),
        )

    async def chat_completion(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int | None = None,
        response_format: dict | None = None,
        tools: list[dict] | None = None,
    ) -> ChatResult:
        kwargs = dict(
            model=model or self.config.model_id,
            messages=messages,
            temperature=temperature,
        )
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        else:
            kwargs["max_tokens"] = self.config.max_output_tokens
        if response_format is not None:
            kwargs["response_format"] = response_format
        if tools is not None:
            kwargs["tools"] = tools

        response = await self._client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        usage = getattr(response, "usage", None)

        # 用量与模型名供 trace 与成本基线使用（docs/specs/us-stage1-trace.md AC3）：
        # 兼容端点不保证回传，取不到就留 None。
        return ChatResult(
            content=choice.message.content,
            input_tokens=getattr(usage, "prompt_tokens", None),
            output_tokens=getattr(usage, "completion_tokens", None),
            model=getattr(response, "model", None),
            finish_reason=getattr(choice, "finish_reason", None),
            tool_calls=_parse_tool_calls(choice),
        )


def _parse_tool_calls(choice) -> list[ToolCall] | None:
    """把 OpenAI 响应里的 tool_calls 解析成 `ToolCall` 列表；没有时为 None。"""
    raw = getattr(choice.message, "tool_calls", None)
    if not raw:
        return None

    parsed: list[ToolCall] = []
    for item in raw:
        raw_arguments = getattr(item.function, "arguments", None)
        try:
            arguments = json.loads(raw_arguments) if raw_arguments else {}
        except (json.JSONDecodeError, TypeError):
            arguments = {}
        parsed.append(ToolCall(id=item.id, name=item.function.name, arguments=arguments))
    return parsed
