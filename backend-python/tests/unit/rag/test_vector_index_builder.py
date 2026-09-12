"""
VectorIndexBuilder 单元测试：用假 repository 验证编排与双写顺序，不碰数据库。

对应规格：docs/specs/us-stage1-embedding.md
"""
from app.entities import Chunk
from app.rag.vector_index_builder import VectorIndexBuilder
from app.services.embedding_service import EmbeddingService

DIMENSION = 8
MODEL_NAME = "fake-embedding-model"


class FakeEmbeddingModel:
    def __init__(self, dimension: int = DIMENSION) -> None:
        self.dimension = dimension
        self.received: list[list[str]] = []

    def embed(self, texts, batch_size=None):
        batch = list(texts)
        self.received.append(batch)
        for index, _ in enumerate(batch):
            yield [float(index)] * self.dimension


class FakeEmbeddingRepository:
    """记录对权威表与索引表的写入调用。"""

    def __init__(self) -> None:
        self.embeddings: list[tuple[str, str, list[float]]] = []
        self.index: list[tuple[str, list[float]]] = []

    def save_for_chunk(self, *, chunk_id: str, embedding_model: str, vector: list[float]):
        self.embeddings.append((chunk_id, embedding_model, vector))

    def save_to_index(self, *, chunk_id: str, vector: list[float]):
        self.index.append((chunk_id, vector))


def make_chunk(chunk_id: str, text: str) -> Chunk:
    return Chunk(
        id=chunk_id,
        document_unit_id="unit-1",
        sequence_index=0,
        text_content=text,
    )


def make_builder(model=None):
    """前缀固定为空：本文件测的是编排与双写顺序，前缀由 embedding_service 的用例覆盖。"""
    model = FakeEmbeddingModel() if model is None else model
    service = EmbeddingService(
        dimension=DIMENSION,
        model_factory=lambda name: model,
        query_prefix="",
        passage_prefix="",
    )
    return VectorIndexBuilder(service, embedding_model=MODEL_NAME), model


def test_build_writes_embedding_and_index_for_each_chunk():
    builder, _ = make_builder()
    repository = FakeEmbeddingRepository()
    chunks = [make_chunk("c1", "premier"), make_chunk("c2", "deuxième")]

    count = builder.build_for_chunks(repository, chunks)

    assert count == 2
    assert [row[0] for row in repository.embeddings] == ["c1", "c2"]
    assert [row[0] for row in repository.index] == ["c1", "c2"]
    assert all(row[1] == MODEL_NAME for row in repository.embeddings)
    assert repository.embeddings[0][2] == repository.index[0][1]


def test_build_writes_authoritative_record_before_index():
    """双写顺序：先权威记录（embedding_vectors），后索引（embedding_index）。"""
    builder, _ = make_builder()
    calls: list[str] = []

    class OrderedRepository:
        def save_for_chunk(self, *, chunk_id: str, embedding_model: str, vector):
            calls.append("embedding")

        def save_to_index(self, *, chunk_id: str, vector):
            calls.append("index")

    builder.build_for_chunks(OrderedRepository(), [make_chunk("c1", "texte")])

    assert calls == ["embedding", "index"]


def test_build_embeds_all_chunk_texts_in_one_batch():
    builder, model = make_builder()
    repository = FakeEmbeddingRepository()

    builder.build_for_chunks(
        repository,
        [make_chunk("c1", "alpha"), make_chunk("c2", "beta")],
    )

    assert model.received == [["alpha", "beta"]]


def test_build_applies_passage_prefix_configured_on_the_service():
    """生产链路给待索引文本加 passage 前缀（e5 要求），且前缀不写进 chunk 存储文本。"""
    model = FakeEmbeddingModel()
    service = EmbeddingService(
        dimension=DIMENSION,
        model_factory=lambda name: model,
        query_prefix="query: ",
        passage_prefix="passage: ",
    )
    builder = VectorIndexBuilder(service, embedding_model=MODEL_NAME)
    chunk = make_chunk("c1", "alpha")

    builder.build_for_chunks(FakeEmbeddingRepository(), [chunk])

    assert model.received == [["passage: alpha"]]
    assert chunk.text_content == "alpha"


def test_build_with_empty_chunk_list_returns_zero_without_loading_model():
    builder, model = make_builder()
    repository = FakeEmbeddingRepository()

    count = builder.build_for_chunks(repository, [])

    assert count == 0
    assert model.received == []
    assert repository.embeddings == []
    assert repository.index == []
