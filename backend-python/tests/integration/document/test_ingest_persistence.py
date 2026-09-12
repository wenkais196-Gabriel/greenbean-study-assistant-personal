"""
摄取端到端：上传 → 落库 → 切块 → 向量化 → **可被检索**。

用真 PDF fixture、真 sqlite-vec（vec0 真建表与真写入）、**假嵌入模型**
（CI 绝不下载模型，见项目的 Rule 3）。这里验证的正是"接料"要保证的闭环：
`DocumentIngestService` 写完之后，`Retriever` 立刻能召回刚入库的片段。
"""
import pytest
from sqlalchemy import select, text

from app.db.init_db import initialize_database, load_sqlite_vec_extension
from app.db.models import (
    ChunkModel,
    DocumentRecordModel,
    DocumentUnitModel,
    EmbeddingVectorModel,
)
from app.db.orm import create_database_engine, create_session_factory
from app.rag.retriever import Retriever
from app.repositories.embedding_repository import EmbeddingRepository
from app.services.document_ingest_service import DocumentIngestService
from app.services.embedding_service import EmbeddingService

pytestmark = [pytest.mark.integration, pytest.mark.us25]

DIMENSION = 8
MODEL_NAME = "fake-embedding-model"
EXPECTED_PAGE_COUNT = 2


class FakeEmbeddingModel:
    """返回按批内顺序递增的确定向量：足以验证"写入—检索"这条通路。"""

    def __init__(self) -> None:
        self.received: list[list[str]] = []

    def embed(self, texts, batch_size=None):
        batch = list(texts)
        self.received.append(batch)
        for index, _ in enumerate(batch):
            yield [float(index) + 1.0] * DIMENSION


@pytest.fixture
def ingest_env(tmp_path):
    """临时库（真 sqlite-vec）+ 假嵌入模型 + 开启完整摄取的 service。"""
    result = initialize_database(
        data_dir=tmp_path / "data",
        database_name="ingest.sqlite3",
        embedding_dimension=DIMENSION,
        sqlite_vec_loader=load_sqlite_vec_extension,
    )
    engine = create_database_engine(
        result.database_path,
        sqlite_vec_loader=load_sqlite_vec_extension,
    )
    session_factory = create_session_factory(engine)

    model = FakeEmbeddingModel()
    embedding_service = EmbeddingService(
        model_name=MODEL_NAME,
        dimension=DIMENSION,
        model_factory=lambda name: model,
        query_prefix="",
        passage_prefix="",
    )
    service = DocumentIngestService(
        session_factory=session_factory,
        embedding_service=embedding_service,
        embedding_model=MODEL_NAME,
        embedding_dimension=DIMENSION,
    )
    try:
        yield service, session_factory, embedding_service, model
    finally:
        engine.dispose()


def test_ingest_persists_document_units_chunks_and_vectors(
    ingest_env,
    text_two_pages_pdf_bytes: bytes,
):
    service, session_factory, _, _ = ingest_env

    result = service.ingest_document(
        "text_two_pages.pdf",
        text_two_pages_pdf_bytes,
        workspace_id="ws-1",
    )

    assert result["chunks_created"] > 0
    assert result["elapsed_seconds"] >= 0

    with session_factory() as session:
        records = session.execute(select(DocumentRecordModel)).scalars().all()
        units = session.execute(select(DocumentUnitModel)).scalars().all()
        chunks = session.execute(select(ChunkModel)).scalars().all()
        vectors = session.execute(select(EmbeddingVectorModel)).scalars().all()
        index_chunk_ids = session.execute(text("SELECT chunk_id FROM embedding_index")).all()

    assert len(records) == 1
    assert records[0].workspace_id == "ws-1"
    assert len(units) == EXPECTED_PAGE_COUNT
    assert len(chunks) == result["chunks_created"]
    assert len(vectors) == len(chunks)  # 权威表：每个片段一条向量
    assert len(index_chunk_ids) == len(chunks)  # 索引副本：双写数量一致


def test_ingested_chunks_are_immediately_retrievable(
    ingest_env,
    text_two_pages_pdf_bytes: bytes,
):
    """"接料"的核心保证：摄取返回之后，检索链路立刻能召回这些片段。"""
    service, session_factory, embedding_service, _ = ingest_env
    service.ingest_document("text_two_pages.pdf", text_two_pages_pdf_bytes)

    with session_factory() as session:
        chunk_ids = set(session.execute(select(ChunkModel.id)).scalars().all())
        repository = EmbeddingRepository(session, embedding_dimension=DIMENSION)
        retriever = Retriever(embedding_service, top_k=5)

        hits = retriever.retrieve(repository, "第 1 页主要讲了什么？")

    assert hits, "摄取后应能检索到片段"
    assert {hit.chunk_id for hit in hits}.issubset(chunk_ids)
    assert all(hit.distance >= 0 for hit in hits)


def test_ingest_embeds_passages_not_queries(
    ingest_env,
    text_two_pages_pdf_bytes: bytes,
):
    """写入侧走的是 passage 文本（此处前缀为空，但数量必须与片段数一致）。"""
    service, _, _, model = ingest_env

    result = service.ingest_document("text_two_pages.pdf", text_two_pages_pdf_bytes)

    embedded_texts = [text_ for batch in model.received for text_ in batch]
    assert len(embedded_texts) == result["chunks_created"]
    assert all(text_.strip() for text_ in embedded_texts)


def test_service_without_session_factory_only_parses(
    tmp_path,
    text_two_pages_pdf_bytes: bytes,
):
    """未注入 session_factory 时保持"只解析"：既不写库、也不加载模型。"""
    result_db = initialize_database(
        data_dir=tmp_path / "data",
        database_name="untouched.sqlite3",
        embedding_dimension=DIMENSION,
        sqlite_vec_loader=load_sqlite_vec_extension,
    )
    engine = create_database_engine(
        result_db.database_path,
        sqlite_vec_loader=load_sqlite_vec_extension,
    )
    session_factory = create_session_factory(engine)
    model = FakeEmbeddingModel()
    service = DocumentIngestService()  # 不注入任何依赖

    try:
        result = service.ingest_document("text_two_pages.pdf", text_two_pages_pdf_bytes)

        with session_factory() as session:
            records = session.execute(select(DocumentRecordModel)).scalars().all()

        assert result["chunks_created"] == 0
        assert result["total_pages"] == EXPECTED_PAGE_COUNT
        assert records == []
        assert model.received == []
    finally:
        engine.dispose()
