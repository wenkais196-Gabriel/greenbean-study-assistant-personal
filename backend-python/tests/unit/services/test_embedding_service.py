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


def make_service(
    model=None,
    *,
    dimension: int = DIMENSION,
    max_chars: int = 1000,
    query_prefix: str = "",
    passage_prefix: str = "",
):
    """默认前缀为空；生产默认值（e5 的 `query: ` / `passage: `）由专门的用例覆盖。"""
    model = FakeEmbeddingModel() if model is None else model
    factory = RecordingModelFactory(model)
    service = EmbeddingService(
        dimension=dimension,
        max_chars=max_chars,
        model_factory=factory,
        query_prefix=query_prefix,
        passage_prefix=passage_prefix,
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


def test_query_and_passage_prefixes_are_applied_before_embedding():
    """e5 系列要求 query / passage 用不同前缀 —— 前缀只能在送模型前拼，不写进存储文本。"""
    service, model, _ = make_service(query_prefix="query: ", passage_prefix="passage: ")

    service.embed_texts(["texte indexé"])
    service.embed_query("question posée")

    assert model.received == [["passage: texte indexé"], ["query: question posée"]]


def test_prefixes_are_empty_by_default_in_tests():
    """不传前缀时行为与从前一致（保证既有断言的语义不变）。"""
    service, model, _ = make_service()

    service.embed_texts(["texte"])

    assert model.received == [["texte"]]


def test_empty_text_list_skips_model_even_with_prefixes():
    service, _, factory = make_service(query_prefix="query: ", passage_prefix="passage: ")

    assert service.embed_texts([]) == []
    assert factory.calls == 0
