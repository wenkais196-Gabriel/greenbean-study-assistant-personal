"""
聊天服务：把"提问"接到检索链路，产出带来源的上下文，再交给 `ChatAgent` 生成回答。

分层（与既有 spec 一致）：
- 本服务负责**同步**基础设施：检索与上下文组装（sqlite + 本地嵌入）；
- `ChatAgent` 只负责路由与 LLM 编排，不碰持久化。

检索与 query 嵌入是同步阻塞的（本地查询毫秒级、嵌入约 30 ms），统一用
`asyncio.to_thread` 丢进线程池 —— 与上传路径同样的处理方式，避免阻塞事件循环。
"""
import asyncio

from app.agents.chat_agent import ChatAgent
from app.config.settings import CONTEXT_MAX_CHARS, EMBEDDING_DIMENSION, RETRIEVAL_TOP_K
from app.db.orm import SessionFactory
from app.enums.route_types import RouteType
from app.rag.context_builder import ContextBuilder
from app.rag.retriever import Retriever
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_unit_repository import DocumentUnitRepository
from app.repositories.embedding_repository import EmbeddingRepository
from app.schemas.chat_schema import ChatRequest, ChatResponse
from app.services.embedding_service import EmbeddingService


class ChatService:
    """提问 → 检索 → 组装上下文 → 生成带来源的回答。"""

    def __init__(
        self,
        *,
        session_factory: SessionFactory,
        agent: ChatAgent | None = None,
        embedding_service: EmbeddingService | None = None,
        top_k: int = RETRIEVAL_TOP_K,
        max_chars: int = CONTEXT_MAX_CHARS,
        embedding_dimension: int = EMBEDDING_DIMENSION,
    ) -> None:
        """
        :param session_factory: 会话工厂（生产走 app/db/runtime，测试注入临时库）
        :param agent: 聊天 Agent，默认 `ChatAgent()`
        :param embedding_service: 嵌入服务，默认懒加载生产配置（**测试请注入假模型**）
        :param top_k: 基础召回深度
        :param max_chars: 上下文预算（见 `ContextBuilder.build_within_budget`）
        """
        self.session_factory = session_factory
        self.agent = agent or ChatAgent()
        self.embedding_service = embedding_service
        self.top_k = top_k
        self.max_chars = max_chars
        self.embedding_dimension = embedding_dimension

    async def answer(self, request: ChatRequest) -> ChatResponse:
        """回答一个问题：先路由（决定策略），再检索，最后生成。"""
        decision = await self.agent.route_question(request.query)
        depth = self._retrieval_depth(decision.route, request.use_extended_context)
        context, sources = await asyncio.to_thread(self._retrieve, request.query, depth)
        return await self.agent.generate_response(
            request,
            context=context,
            sources=sources,
            route=decision,
        )

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
        """同步检索 + 组装（在线程池里执行）：返回 (渲染后的上下文, 来源条目)。"""
        with self.session_factory() as session:
            repository = EmbeddingRepository(
                session, embedding_dimension=self.embedding_dimension
            )
            hits = Retriever(self._get_embedding_service(), top_k=depth).retrieve(
                repository, query
            )

            builder = ContextBuilder(
                ChunkRepository(session),
                DocumentUnitRepository(session),
            )
            selection = builder.build_within_budget(hits, max_chars=self.max_chars)
            context = builder.render(selection.items)

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

    def _get_embedding_service(self) -> EmbeddingService:
        """懒加载生产嵌入服务（测试注入假模型，避免触发模型下载）。"""
        if self.embedding_service is None:
            self.embedding_service = EmbeddingService(dimension=self.embedding_dimension)
        return self.embedding_service
