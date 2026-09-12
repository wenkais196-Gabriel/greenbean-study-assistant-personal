"""
ChatService 单元测试：懒加载嵌入服务的分支。

⚠️ 用 monkeypatch 把 `EmbeddingService` 换成假类 —— 既覆盖了那一行，又**不会真的加载模型**。
"""

from app.services import chat_service as chat_service_module
from app.services.chat_service import ChatService

DIMENSION = 4


class FakeEmbeddingService:
    def __init__(self, dimension: int) -> None:
        self.dimension = dimension


def test_chat_service_lazily_builds_and_reuses_embedding_service(monkeypatch):
    created: list[FakeEmbeddingService] = []

    def fake_embedding_service(dimension: int) -> FakeEmbeddingService:
        service = FakeEmbeddingService(dimension)
        created.append(service)
        return service

    monkeypatch.setattr(chat_service_module, "EmbeddingService", fake_embedding_service)

    service = ChatService(session_factory=lambda: None, embedding_dimension=DIMENSION)

    first = service._get_embedding_service()
    second = service._get_embedding_service()

    assert first is second, "懒加载之后必须复用同一实例"
    assert created == [first]
    assert first.dimension == DIMENSION


def test_chat_service_keeps_injected_embedding_service():
    injected = FakeEmbeddingService(DIMENSION)

    service = ChatService(
        session_factory=lambda: None,
        embedding_service=injected,  # type: ignore[arg-type]
        embedding_dimension=DIMENSION,
    )

    assert service._get_embedding_service() is injected
