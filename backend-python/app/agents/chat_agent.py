"""
聊天 Agent：意图路由 → 拼接检索上下文 → 调 provider 生成回答。

⚠️ 上下文由调用方（`ChatService`）经检索链路产出后**传入**：本 Agent 不碰持久化，
保持"编排 + LLM"的单一职责（分层见 docs/specs/us-stage1-chat.md）。

路由在这里是**真的生效**的：`ChatService` 先用 `route_question()` 拿到意图，再据此决定
召回深度；已算好的决策通过 `route=` 传回来，避免重复调用模型。
"""
from app.agents.classification_agent import RouterAgent
from app.prompts.chat_prompts import CHAT_SYSTEM_PROMPT, CHAT_USER_PROMPT_TPL
from app.providers.registry import ProviderRegistry
from app.schemas.chat_schema import ChatRequest, ChatResponse
from app.schemas.classification_schema import RoutingDecision


class ChatAgent:
    def __init__(self) -> None:
        self.router = RouterAgent()

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
    ) -> ChatResponse:
        """生成回答。

        :param context: 检索链路产出的上下文块（`ContextBuilder.render()` 的结果）；空串表示没有资料
        :param sources: 与上下文块中 `[来源 N]` 一一对应的来源条目，供前端做引用回溯
        :param route: 已经算好的路由决策；不传则本方法自己路由（便于单测与简单调用）
        """
        decision = route if route is not None else await self.route_question(request.query)
        print(f"[CHAT AGENT] 识别到的意图 : {decision.route}")

        provider = ProviderRegistry.get_active()
        response = await provider.chat_completion(
            messages=[
                {"role": "system", "content": CHAT_SYSTEM_PROMPT},
                *[{"role": msg.role, "content": msg.content} for msg in request.history],
                {
                    "role": "user",
                    "content": CHAT_USER_PROMPT_TPL.substitute(
                        context=context,
                        question=request.query,
                    ),
                },
            ],
            temperature=0.3,
        )

        answer = response.content
        return ChatResponse(
            session_id=request.session_id,
            answer=answer,
            source_context=sources,
        )
