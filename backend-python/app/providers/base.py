from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class ToolCall:
    """模型请求的一次工具调用（OpenAI function calling 口径）。

    `arguments` 由 provider 层从 JSON 字符串解析成 dict；解析失败时放空 dict，
    让工具在参数校验环节失败 → 上层 Agent 降级（而不是在 provider 层炸掉）。
    """

    id: str
    name: str
    arguments: dict


class ChatResult:
    """一次 LLM 调用的结果。

    用量字段（token / model / `finish_reason`）都是**可选**的：不是所有 provider 都回传，
    但 trace 与成本基线需要它们（见 docs/specs/us-stage1-trace.md AC10）。
    默认 `None`，既有只传 `content` 的构造方式不受影响。
    `tool_calls` 同理：不支持工具 / 未请求工具时为 `None`。
    """

    def __init__(
        self,
        content: str,
        *,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        model: str | None = None,
        finish_reason: str | None = None,
        tool_calls: list[ToolCall] | None = None,
    ) -> None:
        self.content = content
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.model = model
        self.finish_reason = finish_reason
        self.tool_calls = tool_calls


class AIProvider(ABC):

    @abstractmethod
    async def chat_completion(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int | None = None,
        response_format: dict | None = None,
        tools: list[dict] | None = None,
    ) -> ChatResult:
        """一次对话补全。

        :param tools: OpenAI function calling 口径的工具描述（`{"type": "function", ...}`）；
            `None` 表示不带工具，与既有调用完全一致。
        """
        ...
