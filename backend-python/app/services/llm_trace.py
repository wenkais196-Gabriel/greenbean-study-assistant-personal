"""
LLM 调用的 trace 包装：一次 `chat_completion` 落一条 `gen_ai.*` span。

放在这里而不是 provider 里，是为了让 provider 保持"只会说话"的单一职责 ——
换一个 provider 实现不用重写 trace 逻辑。

字段口径见 docs/specs/us-stage1-trace.md §3.2：对齐 OTel GenAI semconv，
缺失字段**省略**（不是留 null）。
"""
import time
from typing import Any

from app.enums import TraceStatus
from app.providers.base import AIProvider, ChatResult
from app.services.trace_recorder import TraceRecorder, elapsed_ms

SPAN_NAME = "gen_ai.chat"


async def traced_chat_completion(
    provider: AIProvider,
    *,
    messages: list[dict],
    recorder: TraceRecorder | None,
    span_name: str = SPAN_NAME,
    purpose: str | None = None,
    **kwargs: Any,
) -> ChatResult:
    """调用 provider 并把这次调用记成一条 span。

    :param recorder: 为空（trace 关闭）时就是一次直通调用，不产生任何额外行为
    :param purpose: 本次调用的用途（`router` / `answer`），便于在 trace 里区分
    """
    if recorder is None:
        return await provider.chat_completion(messages=messages, **kwargs)

    started = time.perf_counter()
    try:
        result = await provider.chat_completion(messages=messages, **kwargs)
    except Exception as exc:
        recorder.record_span(
            span_name=span_name,
            duration_ms=elapsed_ms(started),
            attributes=_span_attributes(provider, kwargs, None, purpose),
            status=TraceStatus.ERROR,
            error=f"{type(exc).__name__}: {exc}",
        )
        raise

    recorder.record_span(
        span_name=span_name,
        duration_ms=elapsed_ms(started),
        attributes=_span_attributes(provider, kwargs, result, purpose),
    )
    return result


def _string_or_none(value: object) -> str | None:
    """只放行字符串。

    属性最终要 JSON 序列化进 `agent_traces`，而 provider 在测试里常是替身对象 ——
    不设这道闸，一个 MagicMock 就会把整条链路炸在 `json.dumps` 上。
    """
    return value if isinstance(value, str) else None


def _span_attributes(
    provider: AIProvider,
    request_kwargs: dict[str, Any],
    result: ChatResult | None,
    purpose: str | None,
) -> dict[str, Any]:
    """把一次调用映射成 `gen_ai.*` 属性；取不到的字段留 `None`，交给 recorder 丢掉。"""
    config = getattr(provider, "config", None)
    api_mode = getattr(config, "api_mode", None)

    attributes: dict[str, Any] = {
        "gen_ai.operation.name": "chat",
        # semconv 里这里是模型提供方；本项目只有"OpenAI 兼容"这一种模式，就用它
        "gen_ai.system": _string_or_none(getattr(api_mode, "value", None)) or "unknown",
        "gen_ai.request.model": _string_or_none(request_kwargs.get("model"))
        or _string_or_none(getattr(config, "model_id", None)),
        "gen_ai.request.temperature": request_kwargs.get("temperature"),
        "gen_ai.request.max_tokens": request_kwargs.get("max_tokens"),
        "greenbean.purpose": purpose,
    }

    if result is not None:
        attributes.update(
            {
                "gen_ai.response.model": result.model,
                "gen_ai.usage.input_tokens": result.input_tokens,
                "gen_ai.usage.output_tokens": result.output_tokens,
                # semconv 规定是数组
                "gen_ai.response.finish_reasons": (
                    [result.finish_reason] if result.finish_reason else None
                ),
            }
        )

    return attributes
