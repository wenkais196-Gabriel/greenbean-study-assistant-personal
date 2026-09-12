"""
EmbeddingService 单元测试。

全部注入假模型 —— **绝不加载真模型、绝不联网**（CI 不能下载 0.22 GB 模型）。
对应规格：docs/specs/us-stage1-embedding.md
"""
import pytest

from app.repositories.embedding_repository import EmbeddingDimensionError
from app.services.embedding_service import EmbeddingService

DIMENSION = 8


class FakeEmbeddingModel:
    """记录收到的文本，并按顺序返回可区分的向量。"""

    def __init__(self, dimension: int = DIMENSION) -> None:
        self.dimension = dimension
        self.received: list[list[str]] = []

    def embed(self, texts, batch_size=None):
        batch = list(texts)
        self.received.append(batch)
        for index, _ in enumerate(batch):
            yield [float(index)] * self.dimension


class RecordingModelFactory:
    """记录模型被构造了多少次。"""

    def __init__(self, model) -> None:
        self.model = model
        self.calls = 0

    def __call__(self, model_name: str):
        self.calls += 1
        return self.model


def make_service(model=None, *, dimension: int = DIMENSION, max_chars: int = 1000):
    model = FakeEmbeddingModel() if model is None else model
    factory = RecordingModelFactory(model)
    service = EmbeddingService(
        dimension=dimension,
        max_chars=max_chars,
        model_factory=factory,
    )
    return service, model, factory


def test_embed_texts_returns_one_vector_per_text():
    service, _, _ = make_service()

    vectors = service.embed_texts(["premier", "deuxième", "troisième"])

    assert len(vectors) == 3
    assert all(len(vector) == DIMENSION for vector in vectors)


def test_embed_texts_preserves_input_order():
    service, model, _ = make_service()

    service.embed_texts(["premier", "deuxième", "troisième"])

    assert model.received == [["premier", "deuxième", "troisième"]]


def test_empty_text_list_returns_empty_without_loading_model():
    service, _, factory = make_service()

    vectors = service.embed_texts([])

    assert vectors == []
    assert factory.calls == 0


def test_embed_query_returns_single_vector_matching_batch_result():
    service, _, _ = make_service()

    single = service.embed_query("question")
    batch = service.embed_texts(["question"])

    assert len(single) == DIMENSION
    assert single == batch[0]


def test_model_is_loaded_only_once():
    service, _, factory = make_service()

    service.embed_texts(["a"])
    service.embed_texts(["b"])

    assert factory.calls == 1


def test_text_longer_than_limit_is_truncated():
    service, model, _ = make_service(max_chars=100)

    service.embed_texts(["x" * 250])

    assert len(model.received[0][0]) == 100


def test_text_exactly_at_limit_is_not_modified():
    service, model, _ = make_service(max_chars=100)
    text = "y" * 100

    service.embed_texts([text])

    assert model.received[0][0] == text


@pytest.mark.parametrize("dimension", [128, 512])
def test_wrong_dimension_raises(dimension):
    model = FakeEmbeddingModel(dimension=dimension)
    service, _, _ = make_service(model)

    with pytest.raises(EmbeddingDimensionError):
        service.embed_texts(["texte"])


def test_mismatched_vector_count_raises():
    class ShortModel:
        def embed(self, texts, batch_size=None):
            return iter([[0.0] * DIMENSION])

    service, _, _ = make_service(ShortModel())

    with pytest.raises(ValueError):
        service.embed_texts(["a", "b"])
