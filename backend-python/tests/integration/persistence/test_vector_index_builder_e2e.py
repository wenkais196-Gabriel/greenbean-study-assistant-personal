"""
VectorIndexBuilder 端到端测试：**假模型 + 真实数据库**。

验证"嵌入 → 双写 → 可 KNN 命中"这条链路真的接通了。
不下载真模型（CI 安全）。
"""
import pytest

from app.db.init_db import initialize_database, load_sqlite_vec_extension
from app.db.orm import create_database_engine, create_session_factory
from app.entities import Chunk, DocumentRecord, DocumentUnit
from app.enums import DocumentFileType
from app.rag.vector_index_builder import VectorIndexBuilder
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.document_unit_repository import DocumentUnitRepository
from app.repositories.embedding_repository import EmbeddingRepository
from app.services.embedding_service import EmbeddingService

DIMENSION = 8
MODEL_NAME = "fake-embedding-model"
CHUNK_TEXTS = [
    "Le polymorphisme est un concept fondamental.",
    "La classe est un plan de construction des objets.",
]


class DeterministicModel:
    """按文本长度产生确定向量 —— 相同文本必然得到相同向量。"""

    def __init__(self, dimension: int = DIMENSION) -> None:
        self.dimension = dimension

    def embed(self, texts, batch_size=None):
        for text in texts:
            yield [float(len(text) % 7)] * self.dimension


@pytest.fixture
def session_factory(tmp_path):
    result = initialize_database(data_dir=tmp_path / "data", embedding_dimension=DIMENSION)
    engine = create_database_engine(
        result.database_path,
        sqlite_vec_loader=load_sqlite_vec_extension,
    )
    yield create_session_factory(engine)
    engine.dispose()


def seed_chunks(session_factory) -> list[str]:
    """写入 1 个 document + 1 个 unit + 2 个 chunk，返回 chunk id 列表。"""
    document = DocumentRecord(
        workspace_id="workspace_1",
        title="Cours d'algorithmique",
        original_filename="cours.pdf",
        file_type=DocumentFileType.PDF,
        file_path="data/uploads/cours.pdf",
        page_count=1,
    )
    unit = DocumentUnit(
        document_id=document.id,
        sequence_index=0,
        text_content="\n\n".join(CHUNK_TEXTS),
        page_number=1,
    )
    chunks = [
        Chunk(
            id=f"chunk-{index + 1}",
            document_unit_id=unit.id,
            sequence_index=index,
            text_content=text,
        )
        for index, text in enumerate(CHUNK_TEXTS)
    ]
    with session_factory() as session:
        DocumentRepository(session).save(document)
        DocumentUnitRepository(session).save(unit)
        ChunkRepository(session).save_batch(chunks)
        session.commit()
    return [chunk.id for chunk in chunks]


def make_builder() -> VectorIndexBuilder:
    service = EmbeddingService(
        dimension=DIMENSION,
        model_factory=lambda name: DeterministicModel(),
    )
    return VectorIndexBuilder(service, embedding_model=MODEL_NAME)


def test_build_writes_both_tables(session_factory):
    """构建索引后，权威表与索引表各自都有对应记录，且记录了模型名。"""
    chunk_ids = seed_chunks(session_factory)

    with session_factory() as session:
        chunks = [ChunkRepository(session).get_by_id(chunk_id) for chunk_id in chunk_ids]
        count = make_builder().build_for_chunks(
            EmbeddingRepository(session, embedding_dimension=DIMENSION), chunks
        )
        session.commit()

    assert count == len(chunk_ids)

    with session_factory() as session:
        repository = EmbeddingRepository(session, embedding_dimension=DIMENSION)
        for chunk_id in chunk_ids:
            stored = repository.get_by_chunk_id(chunk_id)
            assert stored is not None
            assert stored.embedding_model == MODEL_NAME
            assert stored.vector_dimension == DIMENSION


def test_build_enables_knn_hit_on_own_vector(session_factory):
    """构建后，用某个 chunk 自己的向量查询 top-1 能命中它（距离为 0）。"""
    chunk_ids = seed_chunks(session_factory)

    with session_factory() as session:
        repository = EmbeddingRepository(session, embedding_dimension=DIMENSION)
        chunks = [ChunkRepository(session).get_by_id(chunk_id) for chunk_id in chunk_ids]
        make_builder().build_for_chunks(repository, chunks)
        session.commit()

    target_id = chunk_ids[1]

    with session_factory() as session:
        repository = EmbeddingRepository(session, embedding_dimension=DIMENSION)
        stored = repository.get_by_chunk_id(target_id)
        results = repository.search_similar(stored.vector, top_k=1)

    assert results[0][0] == target_id
    assert results[0][1] == pytest.approx(0.0)


def test_build_is_idempotent(session_factory):
    """对同一批 chunk 重复构建，不产生重复记录。"""
    chunk_ids = seed_chunks(session_factory)

    with session_factory() as session:
        repository = EmbeddingRepository(session, embedding_dimension=DIMENSION)
        chunks = [ChunkRepository(session).get_by_id(chunk_id) for chunk_id in chunk_ids]
        builder = make_builder()
        builder.build_for_chunks(repository, chunks)
        builder.build_for_chunks(repository, chunks)
        session.commit()

    with session_factory() as session:
        repository = EmbeddingRepository(session, embedding_dimension=DIMENSION)
        for chunk_id in chunk_ids:
            assert repository.get_by_chunk_id(chunk_id) is not None
        results = repository.search_similar(
            repository.get_by_chunk_id(chunk_ids[0]).vector, top_k=5
        )

    assert len(results) == len(chunk_ids)


def test_build_with_empty_chunk_list_returns_zero(session_factory):
    """空 chunk 列表返回 0，不产生任何写入。"""
    with session_factory() as session:
        count = make_builder().build_for_chunks(
            EmbeddingRepository(session, embedding_dimension=DIMENSION), []
        )

    assert count == 0
