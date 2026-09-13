"""
聊天 Agent：意图路由 → 拼接检索上下文 → 生成回答；阶段 2 起支持**有界工具循环**。

⚠️ 上下文由调用方（`ChatService`）经检索链路产出后**传入**：本 Agent 不碰持久化，
保持"编排 + LLM"的单一职责（分层见 docs/specs/us-stage1-chat.md）。

工具循环（见 docs/specs/us-stage2-agent-tool-loop.md）：
- 调用方注入 `tool_schemas`（OpenAI function calling 口径）与 `tool_executor` 后，
  模型可以在初始检索上下文**之外**自主调用检索工具补充信息；
- 循环有硬上限（`max_tool_rounds`），且任何工具执行失败 / 超时都会**立即降级**为
  "用已有上下文直答"—— 与 `RouterAgent` 的降级写法同一思路：异常不出给用户。
"""
import asyncio
import json
import time

from app.agents.classification_agent import RouterAgent
from app.config.settings import MAX_TOOL_ROUNDS, TOOL_TIMEOUT_SECONDS
from app.enums import TraceStatus
from app.prompts.chat_prompts import CHAT_SYSTEM_PROMPT, CHAT_USER_PROMPT_TPL
from app.providers.base import AIProvider, ChatResult, ToolCall
from app.providers.registry import ProviderRegistry
from app.schemas.chat_schema import ChatRequest, ChatResponse, ChatUsage
from app.schemas.classification_schema import RoutingDecision
from app.services.llm_trace import traced_chat_completion
from app.services.trace_recorder import TraceRecorder, elapsed_ms


class ChatAgent:
    def __init__(
        self,
        *,
        trace_recorder: TraceRecorder | None = None,
        max_tool_rounds: int = MAX_TOOL_ROUNDS,
        tool_timeout_seconds: float = TOOL_TIMEOUT_SECONDS,
    ) -> None:
        self.trace_recorder = trace_recorder
        self.router = RouterAgent(trace_recorder=trace_recorder)
        self.max_tool_rounds = max_tool_rounds
        self.tool_timeout_seconds = tool_timeout_seconds

    async def route_question(self, query: str) -> RoutingDecision:
        """暴露意图路由：调用方需要在检索**之前**决定策略。"""
        return await self.router.route_question(query)

    async def generate_response(
        self,
        request: ChatRequest,
        *,
        context: str = "",
        sources: list[dict] | None = None,
        route: RoutingDecision | None = None,
        trace_id: str | None = None,
        tool_schemas: list[dict] | None = None,
        tool_executor=None,
    ) -> ChatResponse:
        """生成回答。

        :param context: 检索链路产出的上下文块（`ContextBuilder.render()` 的结果）；空串表示没有资料
        :param sources: 与上下文块中 `[来源 N]` 一一对应的来源条目，供前端做引用回溯
        :param route: 已经算好的路由决策；不传则本方法自己路由（便于单测与简单调用）
        :param trace_id: 本次链路的追踪 ID，原样回填给调用方
        :param tool_schemas: OpenAI function calling 口径的工具描述；`None` 时单轮直答
        :param tool_executor: `ToolExecutor`；与 `tool_schemas` 同时提供时启用工具循环
        """
        decision = route if route is not None else await self.route_question(request.query)
        print(f"[CHAT AGENT] 识别到的意图 : {decision.route}")

        provider = ProviderRegistry.get_active()
        messages = self._base_messages(request, context)

        if tool_schemas and tool_executor:
            loop_messages = list(messages)
            for _ in range(self.max_tool_rounds):
                response = await traced_chat_completion(
                    provider,
                    messages=loop_messages,
                    recorder=self.trace_recorder,
                    purpose="answer",
                    temperature=0.3,
                    tools=tool_schemas,
                )
                if not response.tool_calls:
                    return self._build_response(request, response, sources, trace_id)

                loop_messages.append(self._assistant_tool_call_message(response))
                for tool_call in response.tool_calls:
                    tool_text = await self._execute_tool(tool_call, tool_executor)
                    if tool_text is None:
                        # 执行失败 / 超时：降级为单轮直答（不再带 tools）
                        return await self._fallback_answer(
                            provider, messages, request, sources, trace_id
                        )
                    loop_messages.append(
                        {"role": "tool", "tool_call_id": tool_call.id, "content": tool_text}
                    )
            # 轮数用尽仍要工具：强制直答
            return await self._fallback_answer(provider, messages, request, sources, trace_id)

        response = await traced_chat_completion(
            provider,
            messages=messages,
            recorder=self.trace_recorder,
            purpose="answer",
            temperature=0.3,
        )
        return self._build_response(request, response, sources, trace_id)

    @staticmethod
    def _base_messages(request: ChatRequest, context: str) -> list[dict]:
        return [
            {"role": "system", "content": CHAT_SYSTEM_PROMPT},
            *[{"role": msg.role, "content": msg.content} for msg in request.history],
            {
                "role": "user",
                "content": CHAT_USER_PROMPT_TPL.substitute(
                    context=context,
                    question=request.query,
                ),
            },
        ]

    async def _execute_tool(self, tool_call: ToolCall, tool_executor) -> str | None:
        """执行一次工具调用；成功返回文本，失败 / 超时返回 None 并记一条错误 span。"""
        started = time.perf_counter()
        try:
            async with asyncio.timeout(self.tool_timeout_seconds):
                result = await tool_executor.execute(tool_call)
        except Exception as exc:
            self._record_tool_span(
                tool_call, elapsed_ms(started), error=f"{type(exc).__name__}: {exc}"
            )
            return None
        self._record_tool_span(tool_call, elapsed_ms(started))
        return result

    async def _fallback_answer(
        self,
        provider: AIProvider,
        messages: list[dict],
        request: ChatRequest,
        sources: list[dict] | None,
        trace_id: str | None,
    ) -> ChatResponse:
        """降级：用初始检索上下文做一次普通直答（不带 tools）。"""
        response = await traced_chat_completion(
            provider,
            messages=messages,
            recorder=self.trace_recorder,
            purpose="answer",
            temperature=0.3,
        )
        return self._build_response(request, response, sources, trace_id)

    @staticmethod
    def _build_response(
        request: ChatRequest,
        response: ChatResult,
        sources: list[dict] | None,
        trace_id: str | None,
    ) -> ChatResponse:
        return ChatResponse(
            session_id=request.session_id,
            answer=response.content,
            source_context=sources,
            trace_id=trace_id,
            usage=ChatAgent._usage(response),
        )

    @staticmethod
    def _assistant_tool_call_message(response: ChatResult) -> dict:
        """把模型这轮的 tool_calls 原样 echo 回消息列表（OpenAI 协议要求）。"""
        return {
            "role": "assistant",
            "content": response.content or "",
            "tool_calls": [
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.name,
                        "arguments": json.dumps(tool_call.arguments),
                    },
                }
                for tool_call in response.tool_calls or []
            ],
        }

    def _record_tool_span(
        self,
        tool_call: ToolCall,
        duration_ms: float,
        *,
        error: str | None = None,
    ) -> None:
        if self.trace_recorder is None:
            return
        self.trace_recorder.record_span(
            span_name="greenbean.tool.call",
            duration_ms=duration_ms,
            attributes={"greenbean.tool.name": tool_call.name},
            status=TraceStatus.ERROR if error else TraceStatus.OK,
            error=error,
        )

    @staticmethod
    def _usage(response: ChatResult) -> ChatUsage | None:
        """把 provider 的用量搬进响应；一个都没回传时给 None，不编数字。"""
        if response.input_tokens is None and response.output_tokens is None:
            return None
        return ChatUsage(
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
        )
