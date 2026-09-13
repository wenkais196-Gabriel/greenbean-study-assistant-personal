"""
Retriever 单元测试：用假组件验证编排、阈值与边界。

对应规格：docs/specs/us-stage1-retrieval.md
"""
import pytest

from app.rag.retriever import Retriever

DIMENSION = 8


class FakeEmbeddingService:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def embed_query(self, text: str) -> list[float]:
        self.queries.append(text)
        return [0.1] * DIMENSION


class FakeEmbeddingRepository:
    """按预设结果返回，并记录收到的 top_k 与 workspace_id。"""

    def __init__(self, results: list[tuple[str, float]]) -> None:
        self.results = results
        self.top_k_calls: list[int] = []
        self.workspace_calls: list[str | None] = []

    def search_similar(
        self, vector: list[float], *, top_k: int, workspace_id: str | None = None
    ) -> list[tuple[str, float]]:
        self.top_k_calls.append(top_k)
        self.workspace_calls.append(workspace_id)
        return self.results[:top_k]


def make_retriever(**kwargs):
    service = FakeEmbeddingService()
    return Retriever(service, **kwargs), service


def test_retrieve_returns_at_most_top_k_hits():
    retriever, _ = make_retriever(top_k=2)
    repository = FakeEmbeddingRepository(
        [("c1", 0.0), ("c2", 0.1), ("c3", 0.2)]
    )

    hits = retriever.retrieve(repository, "question")

    assert len(hits) == 2
    assert [hit.chunk_id for hit in hits] == ["c1", "c2"]
    assert repository.top_k_calls == [2]


def test_retrieve_hits_carry_chunk_id_and_distance():
    retriever, _ = make_retriever()
    repository = FakeEmbeddingRepository([("c1", 0.25)])

    hits = retriever.retrieve(repository, "question")

    assert hits[0].chunk_id == "c1"
    assert hits[0].distance == pytest.approx(0.25)


def test_retrieve_drops_hits_beyond_max_distance():
    retriever, _ = make_retriever(max_distance=0.5)
    repository = FakeEmbeddingRepository([("c1", 0.1), ("c2", 0.9)])

    hits = retriever.retrieve(repository, "question")

    assert [hit.chunk_id for hit in hits] == ["c1"]


def test_retrieve_without_max_distance_keeps_all_hits():
    retriever, _ = make_retriever(max_distance=None)
    repository = FakeEmbeddingRepository([("c1", 0.1), ("c2", 99.0)])

    hits = retriever.retrieve(repository, "question")

    assert [hit.chunk_id for hit in hits] == ["c1", "c2"]


def test_retrieve_on_empty_index_returns_empty():
    retriever, _ = make_retriever()
    repository = FakeEmbeddingRepository([])

    assert retriever.retrieve(repository, "question") == []


@pytest.mark.parametrize("blank_query", ["", "   ", "\n\t"])
def test_blank_query_returns_empty_without_embedding(blank_query):
    retriever, service = make_retriever()
    repository = FakeEmbeddingRepository([("c1", 0.0)])

    hits = retriever.retrieve(repository, blank_query)

    assert hits == []
    assert service.queries == []
    assert repository.top_k_calls == []


@pytest.mark.parametrize("top_k", [0, -3])
def test_invalid_top_k_is_rejected(top_k):
    with pytest.raises(ValueError):
        Retriever(FakeEmbeddingService(), top_k=top_k)


def test_retrieve_passes_workspace_filter_through_and_defaults_to_none():
    """`workspace_id` 只透传给 repository：不传 = None（不过滤），传了原样下传。"""
    retriever, _ = make_retriever()
    repository = FakeEmbeddingRepository([("c1", 0.0)])

    retriever.retrieve(repository, "question")
    retriever.retrieve(repository, "question", workspace_id="ws-a")

    assert repository.workspace_calls == [None, "ws-a"]
