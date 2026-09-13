"""
聊天服务：把"提问"接到检索链路，产出带来源的上下文，再交给 `ChatAgent` 生成回答。

分层（与既有 spec 一致）：
- 本服务负责**同步**基础设施：检索、上下文组装（sqlite + 本地嵌入）与**落库**；
- `ChatAgent` 只负责路由与 LLM 编排，不碰持久化。

检索与 query 嵌入是同步阻塞的（本地查询毫秒级、嵌入约 30 ms），统一用
`asyncio.to_thread` 丢进线程池 —— 与上传路径同样的处理方式，避免阻塞事件循环。

trace（见 docs/specs/us-stage1-trace.md）：本服务产出 `agent.route` / `retrieval.search` /
`context.build` 三条 span，并把 `trace_id` 回填给调用方；LLM 调用由 agent 经
`traced_chat_completion` 记录。阶段 2 起，本服务还负责装配工具执行器
（见 docs/specs/us-stage2-agent-tool-loop.md）。
"""
import asyncio
import time

from app.agents.chat_agent import ChatAgent
from app.agents.tool_executor import ToolExecutor
from app.config.settings import CONTEXT_MAX_CHARS, EMBEDDING_DIMENSION, RETRIEVAL_TOP_K
from app.db.orm import SessionFactory
from app.entities import ChatMessage
from app.enums.route_types import RouteType
from app.rag.context_builder import ContextBuilder
from app.rag.retriever import Retriever
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_unit_repository import DocumentUnitRepository
from app.repositories.embedding_repository import EmbeddingRepository
from app.schemas.chat_schema import ChatRequest, ChatResponse
from app.schemas.classification_schema import RoutingDecision
from app.services.chat_session_service import DEFAULT_WORKSPACE_ID, ChatSessionService
from app.services.embedding_service import EmbeddingService
from app.services.trace_recorder import TraceRecorder, elapsed_ms
from app.tools.factory import build_tools
from app.tools.schemas import RETRIEVAL_TOOL_SCHEMAS
from app.utils.trace_context import bind_trace, current_trace_id, reset_trace


class ChatService:
    """提问 → 检索 → 组装上下文 → 生成带来源的回答 → 落库。"""

    def __init__(
        self,
        *,
        session_factory: SessionFactory,
        agent: ChatAgent | None = None,
        embedding_service: EmbeddingService | None = None,
        session_service: ChatSessionService | None = None,
        top_k: int = RETRIEVAL_TOP_K,
        max_chars: int = CONTEXT_MAX_CHARS,
        embedding_dimension: int = EMBEDDING_DIMENSION,
        trace_recorder: TraceRecorder | None = None,
    ) -> None:
        """
        :param session_factory: 会话工厂（生产走 app/db/runtime，测试注入临时库）
        :param agent: 聊天 Agent，默认 `ChatAgent()`（会拿到同一个 trace recorder）
        :param embedding_service: 嵌入服务，默认懒加载生产配置（**测试请注入假模型**）
        :param session_service: 会话落库服务，默认用同一个 `session_factory` 构造（构造时不碰磁盘）
        :param top_k: 基础召回深度
        :param max_chars: 上下文预算（见 `ContextBuilder.build_within_budget`）
        :param trace_recorder: 结构化 trace 记录器；`None` 表示不记录（trace 关闭时传 None）
        """
        self.session_factory = session_factory
        self.trace_recorder = trace_recorder
        self.agent = agent or ChatAgent(trace_recorder=trace_recorder)
        self.embedding_service = embedding_service
        self.session_service = session_service or ChatSessionService(
            session_factory=session_factory
        )
        self.top_k = top_k
        self.max_chars = max_chars
        self.embedding_dimension = embedding_dimension
        self._tool_executor: ToolExecutor | None = None

    async def answer(self, request: ChatRequest) -> ChatResponse:
        """回答一个问题：先路由（决定策略），再检索，最后生成并落库。

        整个链路的 span 共享同一个 `trace_id`（存在 contextvar 里），
        并回填到响应的 `trace_id` 上供调用方取回全貌（AC2）。

        ⚠️ 落库放在**回答成功之后**、且自成事务：SQLite 单写者，不能在检索的读事务里写别的表。
        提问失败（如 provider 未配置）时不落库，历史里不会留下半截会话。
        """
        token = bind_trace()
        try:
            trace_id = current_trace_id()
            decision = await self._route(request.query)
            depth = self._retrieval_depth(decision.route, request.use_extended_context)
            context, sources = await asyncio.to_thread(self._retrieve, request.query, depth)
            response = await self.agent.generate_response(
                request,
                context=context,
                sources=sources,
                route=decision,
                trace_id=trace_id,
                tool_schemas=RETRIEVAL_TOOL_SCHEMAS,
                tool_executor=self._get_tool_executor(),
            )
            await asyncio.to_thread(self._persist, request, response)
            return response
        finally:
            reset_trace(token)

    def list_session_messages(self, session_id: str) -> list[ChatMessage] | None:
        """回读会话历史；会话不存在时返回 `None`。"""
        return self.session_service.list_messages(session_id)

    def _persist(self, request: ChatRequest, response: ChatResponse) -> None:
        """同步落库（在线程池里执行）。"""
        self.session_service.append_turn(
            session_id=request.session_id,
            workspace_id=request.workspace_id or DEFAULT_WORKSPACE_ID,
            query=request.query,
            answer=response.answer,
            source_context=response.source_context or [],
        )

    async def _route(self, query: str) -> RoutingDecision:
        """路由 + 记录 `agent.route` span。

        不需要 try/except：`RouterAgent` 自己吞掉一切异常并降级返回，
        降级与否体现在 `greenbean.route.degraded` 上（降级率是个有用的健康指标）。
        """
        started = time.perf_counter()
        decision = await self.agent.route_question(query)
        self._record(
            "agent.route",
            elapsed_ms(started),
            **{
                "greenbean.route": decision.route.value,
                "greenbean.route.degraded": decision.degraded,
            },
        )
        return decision

    def _retrieval_depth(self, route: RouteType, extended: bool) -> int:
        """按意图与"扩展上下文"开关决定召回深度。

        - `COMPREHENSIVE`（综合/复习类）通常要拼接多段材料 → 双倍候选；
        - `STRUCTURE`（页码/大纲类）目前在数据层**还没有章节或页码检索能力**，暂与概念类同深度，
          记为待办（见 docs/specs/us-stage1-chat.md §5）。
        """
        if route is RouteType.COMPREHENSIVE or extended:
            return self.top_k * 2
        return self.top_k

    def _retrieve(self, query: str, depth: int) -> tuple[str, list[dict]]:
        """同步检索 + 组装（在线程池里执行）：返回 (渲染后的上下文, 来源条目)。

        ⚠️ span **在 `with` 块之外**写：读事务持 SHARED 锁，此时另一个连接去写
        `agent_traces` 会卡在锁 Upgrade 上（SQLite 单写者，见 docs/specs/us-stage1-trace.md §3.4）。
        所以先在事务里把数据与耗时都取出来，出了 `with` 再落 span。
        """
        with self.session_factory() as session:
            repository = EmbeddingRepository(
                session, embedding_dimension=self.embedding_dimension
            )
            retrieval_started = time.perf_counter()
            hits = Retriever(self._get_embedding_service(), top_k=depth).retrieve(
                repository, query
            )
            retrieval_ms = elapsed_ms(retrieval_started)

            builder = ContextBuilder(
                ChunkRepository(session),
                DocumentUnitRepository(session),
            )
            build_started = time.perf_counter()
            selection = builder.build_within_budget(hits, max_chars=self.max_chars)
            context = builder.render(selection.items)
            build_ms = elapsed_ms(build_started)

        self._record(
            "retrieval.search",
            retrieval_ms,
            **{
                "greenbean.retrieval.top_k": depth,
                "greenbean.retrieval.hits": len(hits),
            },
        )
        self._record(
            "context.build",
            build_ms,
            **{
                "greenbean.context.items": len(selection.items),
                "greenbean.context.chars": len(context),
                "greenbean.context.dropped": len(selection.dropped_chunk_ids),
            },
        )

        sources = [
            {
                "chunk_id": item.chunk_id,
                "document_id": item.document_id,
                "page_number": item.page_number,
                "heading_path": item.heading_path,
                "distance": item.distance,
            }
            for item in selection.items
        ]
        return context, sources

    def _record(self, span_name: str, duration_ms: float, **attributes: object) -> None:
        """写一条 span；没接 recorder 时什么都不做。"""
        if self.trace_recorder is None:
            return
        self.trace_recorder.record_span(
            span_name=span_name,
            duration_ms=duration_ms,
            attributes=dict(attributes),
        )

    def _get_tool_executor(self) -> ToolExecutor:
        """懒加载工具执行器：三个检索工具接生产（复用同一会话工厂与嵌入服务）。"""
        if self._tool_executor is None:
            toolset = build_tools(
                session_factory=self.session_factory,
                embedding_service=self._get_embedding_service(),
                provider=None,
                embedding_dimension=self.embedding_dimension,
            )
            self._tool_executor = ToolExecutor(
                {
                    "chunk_search_tool": toolset.chunk_search,
                    "document_retrieval_tool": toolset.document_retrieval,
                    "section_context_tool": toolset.section_context,
                }
            )
        return self._tool_executor

    def _get_embedding_service(self) -> EmbeddingService:
        """懒加载生产嵌入服务（测试注入假模型，避免触发模型下载）。"""
        if self.embedding_service is None:
            self.embedding_service = EmbeddingService(dimension=self.embedding_dimension)
        return self.embedding_service
