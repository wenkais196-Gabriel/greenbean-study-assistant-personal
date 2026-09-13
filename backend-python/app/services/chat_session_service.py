"""
问答会话与消息的持久化。

分层：`ChatService` 负责"提问 → 检索 → 回答"的编排，本服务只负责把一轮问答**落库**
（会话自动建、消息逐条追加），让刷新或重开界面后历史还在、引用可回溯。

⚠️ SQLite 单写者（本项目已踩过两次）：写操作必须**各自成事务**，绝不在检索的读事务里调用，
否则同一个线程持着读锁去写别的表必然 `database is locked`，加 `busy_timeout` 也没用。
见 docs/specs/us-stage1-trace.md §3.4。
"""
from datetime import datetime, timezone

from app.db.orm import SessionFactory
from app.entities import ChatMessage, ChatSession
from app.enums.message_role import MessageRole
from app.repositories.chat_message_repository import ChatMessageRepository
from app.repositories.chat_session_repository import ChatSessionRepository

#: 缺省工作区：请求不带 `workspace_id` 时用它归档。
#: 与前端 `src/features/chat/api/chatApi.ts` 的 `DEFAULT_WORKSPACE_ID` 保持一致。
DEFAULT_WORKSPACE_ID = "default"

#: 会话标题长度上限（取首问前 N 字）：够看出是哪次对话即可。
SESSION_TITLE_MAX_CHARS = 30


class ChatSessionService:
    """一轮问答的落库与历史回读。"""

    def __init__(self, *, session_factory: SessionFactory) -> None:
        self.session_factory = session_factory

    def append_turn(
        self,
        *,
        session_id: str,
        workspace_id: str,
        query: str,
        answer: str,
        source_context: list[dict],
    ) -> None:
        """把一轮问答落库：会话不存在则建（标题取首问），随后追加两条消息。

        :param source_context: 回答引用的来源条目；以 `{"sources": [...]}` 存入
            `source_context_json`（实体该字段是 dict，来源本身是列表）
        """
        now = datetime.now(timezone.utc)
        with self.session_factory() as session:
            sessions = ChatSessionRepository(session)
            existing = sessions.get_by_id(session_id)
            if existing is None:
                sessions.save(
                    ChatSession(
                        id=session_id,
                        workspace_id=workspace_id,
                        title=query[:SESSION_TITLE_MAX_CHARS],
                        created_at=now,
                        updated_at=now,
                    )
                )
            else:
                existing.updated_at = now
                sessions.save(existing)

            messages = ChatMessageRepository(session)
            messages.save(
                ChatMessage(
                    session_id=session_id,
                    role=MessageRole.USER,
                    content=query,
                    created_at=now,
                )
            )
            messages.save(
                ChatMessage(
                    session_id=session_id,
                    role=MessageRole.AGENT,
                    content=answer,
                    source_context_json={"sources": source_context},
                    created_at=now,
                )
            )
            session.commit()

    def list_messages(self, session_id: str) -> list[ChatMessage] | None:
        """回读会话历史；会话不存在时返回 `None`（调用方据此回 404）。"""
        with self.session_factory() as session:
            if ChatSessionRepository(session).get_by_id(session_id) is None:
                return None
            return ChatMessageRepository(session).list_by_session(session_id)
