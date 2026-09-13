"""
检索适配器（把生产检索接到 ChunkSearchTool 协议上）的集成测试。

对应规格：docs/specs/us-stage2-tools-wiring.md

用**真**临时库 + 真 sqlite-vec，只把 embedding 模型换成"永远返回同一个向量"的假模型 ——
本批要验证的正是"按 workspace 过滤的 SQL 真的对"，用 mock 掉 repository 会把要暴露的问题掩盖掉。

⚠️ 关于"要不要过采样"：sqlite-vec 的过滤语义**取决于查询写法**（实测）—— 子查询 IN 是
pre-filter（`k` 作用在过滤**之后**，本文件与适配器用的就是它，因此**不需要过采样**），
而 JOIN / 字面量 IN 是 post-filter（`k` 先切、再过滤）。该语义由
tests/integration/persistence/test_vector_index.py 独立锁定，改动查询写法会让它先红。
"""
import sqlite3

import pytest
import sqlite_vec
from sqlalchemy import text

from app.db.init_db import initialize_database
from app.db.orm import create_database_engine, create_session_factory
from app.entities import AnalysisResult, Chunk, DocumentRecord, DocumentUnit
from app.enums import AnalysisType, DocumentFileType
from app.repositories.analysis_result_repository import AnalysisResultRepository
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.document_unit_repository import DocumentUnitRepository
from app.repositories.embedding_repository import EmbeddingRepository
from app.services.embedding_service import EmbeddingService
from app.tools import adapters
from app.tools.adapters import (
    ProductionChunkSearcher,
    SessionScopedAnalysisResultRepository,
    SessionScopedDocumentRepository,
    SessionScopedSectionRepository,
)

DIMENSION = 8
QUERY_VECTOR = [1.0] * DIMENSION
EXPECTED_FIELDS = {"chunk_id", "text", "document_id", "page_number", "heading_path", "distance"}


def load_test_sqlite_vec(connection: sqlite3.Connection) -> None:
    """真加载 sqlite-vec（vec0 模块是建索引表的前提），但把 vec_version 覆盖为固定测试值。"""
    connection.enable_load_extension(True)
    try:
        sqlite_vec.load(connection)
    finally:
        connection.enable_load_extension(False)
    connection.create_function("vec_version", 0, lambda: "test-sqlite-vec")


class FixedEmbeddingModel:
    """忽略文本内容、永远返回同一个向量的假模型（CI 不下载 2.2 GB 真模型）。"""

    def __init__(self, vector: list[float]) -> None:
        self.vector = vector

    def embed(self, texts, batch_size=None):  # noqa: ARG002 - 签名对齐 fastembed 的 TextEmbedding
        return [list(self.vector) for _ in texts]


@pytest.fixture
def session_factory(tmp_path):
    result = initialize_database(
        data_dir=tmp_path / "data",
        sqlite_vec_loader=load_test_sqlite_vec,
        embedding_dimension=DIMENSION,
    )
    engine = create_database_engine(
        result.database_path,
        sqlite_vec_loader=load_test_sqlite_vec,
    )
    yield create_session_factory(engine)
    engine.dispose()


def seed_chunk(
    session_factory,
    *,
    workspace_id: str,
    chunk_id: str,
    vector: list[float],
    text: str | None = None,
) -> str:
    """写入 DocumentRecord + DocumentUnit + Chunk 并建索引，返回 document_id。"""
    text = text or f"contenu de {chunk_id}"
    document = DocumentRecord(
        workspace_id=workspace_id,
        title=f"Cours {workspace_id}",
        original_filename=f"{workspace_id}.pdf",
        file_type=DocumentFileType.PDF,
        file_path=f"data/uploads/{workspace_id}.pdf",
        page_count=1,
    )
    unit = DocumentUnit(
        document_id=document.id,
        sequence_index=0,
        text_content=text,
        page_number=1,
    )
    chunk = Chunk(
        id=chunk_id,
        document_unit_id=unit.id,
        sequence_index=0,
        text_content=text,
    )
    with session_factory() as session:
        DocumentRepository(session).save(document)
        DocumentUnitRepository(session).save(unit)
        ChunkRepository(session).save(chunk)
        EmbeddingRepository(session, embedding_dimension=DIMENSION).save_to_index(
            chunk_id=chunk_id, vector=vector
        )
        session.commit()
    return document.id


def make_searcher(session_factory, *, query_vector: list[float] | None = None) -> ProductionChunkSearcher:
    return ProductionChunkSearcher(
        session_factory=session_factory,
        embedding_service=EmbeddingService(
            dimension=DIMENSION,
            model_factory=lambda _name: FixedEmbeddingModel(query_vector or QUERY_VECTOR),
        ),
        embedding_dimension=DIMENSION,
    )


def search(session_factory, *, workspace_id: str, top_k: int = 5, query: str = "graphe"):
    return make_searcher(session_factory).search(query=query, workspace_id=workspace_id, top_k=top_k)


# --- 检索行为 ---


@pytest.mark.us("US-STAGE2-TOOLS-01")
def test_search_without_workspace_returns_hits_from_every_workspace(session_factory):
    """workspace_id 为空 = 不按 workspace 过滤，行为与生产检索一致。"""
    seed_chunk(session_factory, workspace_id="ws-a", chunk_id="a1", vector=[1.0] * DIMENSION)
    seed_chunk(session_factory, workspace_id="ws-b", chunk_id="b1", vector=[0.9] * DIMENSION)

    results = search(session_factory, workspace_id="")

    assert {hit["chunk_id"] for hit in results} == {"a1", "b1"}


@pytest.mark.us("US-STAGE2-TOOLS-01")
def test_search_filters_hits_by_workspace(session_factory):
    """指定 workspace 后只返回该 workspace 的片段 —— 其它 workspace 的片段再像也不给。"""
    seed_chunk(session_factory, workspace_id="ws-a", chunk_id="a1", vector=[0.5] * DIMENSION)
    seed_chunk(session_factory, workspace_id="ws-b", chunk_id="b1", vector=[1.0] * DIMENSION)

    results = search(session_factory, workspace_id="ws-a")

    assert [hit["chunk_id"] for hit in results] == ["a1"]


@pytest.mark.us("US-STAGE2-TOOLS-01")
def test_search_finds_workspace_hits_that_rank_late_globally(session_factory):
    """本 workspace 的片段排在全局较后时也要召回，且**不需要过采样**。

    生产查询用的是**子查询**过滤，sqlite-vec 实测为 pre-filter：`k` 作用在过滤**之后**，
    因此 `top_k=1` 也能拿到全局第 7 名的本 workspace 片段。
    该语义由 tests/integration/persistence/test_vector_index.py 独立锁定。
    """
    # ws-b 的 6 个片段离 query 更近，占据全局前 6 名；ws-a 的片段排第 7。
    for index in range(6):
        seed_chunk(
            session_factory,
            workspace_id="ws-b",
            chunk_id=f"b{index}",
            vector=[0.99 - index * 0.01] * DIMENSION,
        )
    seed_chunk(session_factory, workspace_id="ws-a", chunk_id="a1", vector=[0.5] * DIMENSION)

    narrowed = search(session_factory, workspace_id="ws-a", top_k=1)
    default = search(session_factory, workspace_id="ws-a", top_k=5)

    assert [hit["chunk_id"] for hit in narrowed] == ["a1"]
    assert [hit["chunk_id"] for hit in default] == ["a1"]


@pytest.mark.us("US-STAGE2-TOOLS-01")
def test_search_returns_at_most_top_k_results(session_factory):
    """返回条数不超过调用方要的 top_k。"""
    for index in range(3):
        seed_chunk(
            session_factory,
            workspace_id="ws-a",
            chunk_id=f"a{index}",
            vector=[0.9 - index * 0.1] * DIMENSION,
        )

    results = search(session_factory, workspace_id="ws-a", top_k=2)

    assert [hit["chunk_id"] for hit in results] == ["a0", "a1"]


@pytest.mark.us("US-STAGE2-TOOLS-01")
def test_search_lazily_builds_the_production_embedding_service(session_factory, monkeypatch):
    """不注入嵌入服务时自己造一个 —— 构造不加载模型权重（首次 embed 才加载）。

    这里把 `EmbeddingService` 换成"假模型 + 测试维度"的构造：既走通懒加载分支，
    又不会在 CI 下载 2.2 GB 的真模型。
    """
    seed_chunk(session_factory, workspace_id="ws-a", chunk_id="a1", vector=[1.0] * DIMENSION)
    monkeypatch.setattr(
        adapters,
        "EmbeddingService",
        lambda **_kwargs: EmbeddingService(
            dimension=DIMENSION,
            model_factory=lambda _name: FixedEmbeddingModel(QUERY_VECTOR),
        ),
    )
    searcher = adapters.ProductionChunkSearcher(
        session_factory=session_factory, embedding_dimension=DIMENSION
    )

    results = searcher.search(query="graphe", workspace_id="ws-a")

    assert [hit["chunk_id"] for hit in results] == ["a1"]


@pytest.mark.us("US-STAGE2-TOOLS-01")
def test_search_returns_source_fields_needed_for_citation(session_factory):
    """返回条目要能支撑引用回溯：片段、文档、页码、章节路径、距离一个都不能少。"""
    document_id = seed_chunk(
        session_factory,
        workspace_id="ws-a",
        chunk_id="a1",
        vector=[1.0] * DIMENSION,
        text="Le polymorphisme est un concept fondamental.",
    )

    hit = search(session_factory, workspace_id="ws-a")[0]

    assert set(hit) == EXPECTED_FIELDS
    assert hit["chunk_id"] == "a1"
    assert hit["text"] == "Le polymorphisme est un concept fondamental."
    assert hit["document_id"] == document_id
    assert hit["page_number"] == 1
    assert hit["heading_path"] == []
    assert hit["distance"] == pytest.approx(0.0)


@pytest.mark.us("US-STAGE2-TOOLS-01")
def test_search_blank_query_returns_empty_without_loading_the_model(session_factory):
    """空白查询返回空列表，且不触发模型加载（模型工厂一旦被调用就抛错）。"""
    seed_chunk(session_factory, workspace_id="ws-a", chunk_id="a1", vector=[1.0] * DIMENSION)
    searcher = ProductionChunkSearcher(
        session_factory=session_factory,
        embedding_service=EmbeddingService(
            dimension=DIMENSION,
            model_factory=lambda _name: pytest.fail("空白查询不该加载 embedding 模型"),
        ),
    )

    assert searcher.search(query="   ", workspace_id="ws-a", top_k=5) == []


@pytest.mark.us("US-STAGE2-TOOLS-01")
@pytest.mark.parametrize("bad_top_k", [0, -3])
def test_search_rejects_non_positive_top_k(session_factory, bad_top_k):
    """top_k 非法时明确报错，而不是静默返回空结果让调用方以为"没搜到"。"""
    with pytest.raises(ValueError, match="top_k"):
        search(session_factory, workspace_id="ws-a", top_k=bad_top_k)


@pytest.mark.us("US-STAGE2-TOOLS-01")
def test_search_skips_hits_whose_source_rows_are_gone(session_factory):
    """索引与权威表不同步时跳过孤儿命中，而不是返回一条没有来源的空条目。"""
    with session_factory() as session:
        session.execute(
            text("INSERT INTO embedding_index(chunk_id, embedding) VALUES (:id, :vec)"),
            {"id": "orphan", "vec": "[" + ",".join(["1.0"] * DIMENSION) + "]"},
        )
        session.commit()

    assert search(session_factory, workspace_id="") == []


# --- session 作用域的仓储代理 ---


@pytest.mark.us("US-STAGE2-TOOLS-02")
def test_session_scoped_document_repository_reads_document_by_id(session_factory):
    """工具持有的是长期对象，而生产 repository 绑定单个 session → 代理每次调用自开 session。"""
    document_id = seed_chunk(session_factory, workspace_id="ws-a", chunk_id="a1", vector=[1.0] * DIMENSION)

    loaded = SessionScopedDocumentRepository(session_factory).get_by_id(document_id)

    assert loaded is not None
    assert loaded.id == document_id
    assert loaded.workspace_id == "ws-a"


@pytest.mark.us("US-STAGE2-TOOLS-02")
def test_session_scoped_document_repository_returns_none_for_unknown_id(session_factory):
    assert SessionScopedDocumentRepository(session_factory).get_by_id("missing") is None


@pytest.mark.us("US-STAGE2-TOOLS-02")
def test_session_scoped_analysis_result_repository_reads_by_workspace(session_factory):
    """分析结果没有 workspace 列，要经 document_records 关联过滤。"""
    document_id = seed_chunk(session_factory, workspace_id="ws-a", chunk_id="a1", vector=[1.0] * DIMENSION)
    other_document_id = seed_chunk(
        session_factory, workspace_id="ws-b", chunk_id="b1", vector=[1.0] * DIMENSION
    )
    with session_factory() as session:
        AnalysisResultRepository(session).save(
            AnalysisResult(
                document_id=document_id,
                analysis_type=AnalysisType.FULL_DOCUMENT,
                language="zh",
                content_markdown="全文分析",
                summary="全文摘要",
            )
        )
        AnalysisResultRepository(session).save(
            AnalysisResult(
                document_id=other_document_id,
                analysis_type=AnalysisType.FULL_DOCUMENT,
                language="zh",
                content_markdown="另一个工作区",
                summary="另一个摘要",
            )
        )
        session.commit()

    results = SessionScopedAnalysisResultRepository(session_factory).get_by_workspace_id("ws-a")

    assert [result.summary for result in results] == ["全文摘要"]


@pytest.mark.us("US-STAGE2-TOOLS-02")
def test_session_scoped_section_repository_returns_none_for_unknown_id(session_factory):
    """本节没有小节数据 —— 代理仍要给出"查不到"而不是抛异常。"""
    assert SessionScopedSectionRepository(session_factory).get_by_id("missing") is None
