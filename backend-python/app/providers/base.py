from abc import ABC, abstractmethod


class ChatResult:
    """一次 LLM 调用的结果。

    用量字段（token / model / `finish_reason`）都是**可选**的：不是所有 provider 都回传，
    但 trace 与成本基线需要它们（见 docs/specs/us-stage1-trace.md AC10）。
    默认 `None`，既有只传 `content` 的构造方式不受影响。
    """

    def __init__(
        self,
        content: str,
        *,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        model: str | None = None,
        finish_reason: str | None = None,
    ) -> None:
        self.content = content
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.model = model
        self.finish_reason = finish_reason


class AIProvider(ABC):

    @abstractmethod
    async def chat_completion(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int | None = None,
        response_format: dict | None = None,
    ) -> ChatResult:
        ...
