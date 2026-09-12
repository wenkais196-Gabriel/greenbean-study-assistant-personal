import json

from app.enums.route_types import RouteType
from app.prompts.classification_prompts import ROUTER_SYSTEM_PROMPT
from app.providers.registry import ProviderRegistry
from app.schemas.classification_schema import RoutingDecision
from app.services.llm_trace import traced_chat_completion
from app.services.trace_recorder import TraceRecorder


class RouterAgent:
    def __init__(self, *, trace_recorder: TraceRecorder | None = None) -> None:
        self.trace_recorder = trace_recorder

    async def route_question(self, user_question: str) -> RoutingDecision:
        try:
            provider = ProviderRegistry.get_active()
            response = await traced_chat_completion(
                provider,
                messages=[
                    {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"Question de l'étudiant : {user_question}",
                    },
                ],
                recorder=self.trace_recorder,
                purpose="router",
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            result_str = response.content
            result_dict = json.loads(result_str)
            decision = RoutingDecision(**result_dict)

            print(f"[LOG AGENT] Question: '{user_question}' -> Route: {decision.route}")
            return decision

        except Exception as e:
            print(f"[ERREUR AGENT] 路由分发失败，自动降级处理 : {str(e)}")
            # `degraded=True` 让"降级率"成为可统计的指标（见 docs/specs/us-stage1-trace.md AC3）
            return RoutingDecision(
                route=RouteType.COMPREHENSIVE,
                reason=f"调用 API 时发生技术错误 : {str(e)}",
                degraded=True,
            )
