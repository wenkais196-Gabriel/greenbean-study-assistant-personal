"""
本地向量索引（sqlite-vec + vec0）集成测试。

对应规格：docs/specs/us-stage1-vector-index.md

与既有的 persistence 测试不同，这里**不注入假 loader** —— 这批要验证的正是
"真实初始化路径可用"，用假 loader 会把要暴露的问题掩盖掉。
"""
import pytest
from sqlalchemy import text

from app.db.init_db import (
    SQLiteVecInitializationError,
    initialize_database,
    load_sqlite_vec_extension,
)
from app.db.orm import create_database_engine, create_session_factory
from app.entities import Chunk, DocumentRecord, DocumentUnit
from app.enums import DocumentFileType
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.document_unit_repository import DocumentUnitRepository
from app.repositories.embedding_repository import (
    EmbeddingDimensionError,
    EmbeddingRepository,
    MissingChunkError,
)

DIMENSION = 384


def make_vector(seed: float) -> list[float]:
    """构造一个所有分量相同的简单向量，便于断言距离关系。"""
    return [seed] * DIMENSION


def to_vec0_literal(vector: list[float]) -> str:
    """vec0 接受 JSON 数组形式的字符串字面量。"""
    return "[" + ",".join(str(value) for value in vector) + "]"


@pytest.fixture
def session_factory(tmp_path):
    """使用**默认** loader 初始化数据库，并返回会话工厂。"""
    result = initialize_database(
        data_dir=tmp_path / "data",
        embedding_dimension=DIMENSION,
    )
    engine = create_database_engine(
        result.database_path,
        sqlite_vec_loader=load_sqlite_vec_extension,
    )
    yield create_session_factory(engine)
    engine.dispose()


def seed_chunk(
    session_factory, *, chunk_id: str = "chunk-1", workspace_id: str = "workspace_1"
) -> str:
    """经 repository 写入 DocumentRecord + DocumentUnit + Chunk，返回 chunk_id。"""
    document = DocumentRecord(
        workspace_id=workspace_id,
        title="Cours d'algorithmique",
        original_filename="cours.pdf",
        file_type=DocumentFileType.PDF,
        file_path="data/uploads/cours.pdf",
        page_count=1,
    )
    unit = DocumentUnit(
        document_id=document.id,
        sequence_index=0,
        text_content="Le polymorphisme est un concept fondamental.",
        page_number=1,
    )
    chunk = Chunk(
        id=chunk_id,
        document_unit_id=unit.id,
        sequence_index=0,
        text_content="Le polymorphisme est un concept fondamental.",
    )
    with session_factory() as session:
        DocumentRepository(session).save(document)
        DocumentUnitRepository(session).save(unit)
        ChunkRepository(session).save(chunk)
        session.commit()
    return chunk_id


def test_initialize_database_loads_sqlite_vec_for_real(tmp_path):
    """默认 loader 能真正加载 sqlite-vec，并返回版本号。"""
    result = initialize_database(
        data_dir=tmp_path / "data",
        embedding_dimension=DIMENSION,
    )

    assert result.persistence_ready is True
    assert isinstance(result.sqlite_vec_version, str)
    assert result.sqlite_vec_version.strip()


def test_embedding_index_table_exists_and_accepts_configured_dimension(session_factory):
    """初始化后存在 embedding_index 虚拟表，且接受配置维度的向量。"""
    with session_factory() as session:
        tables = session.execute(
            text("SELECT name FROM sqlite_master WHERE name = 'embedding_index'")
        ).scalars().all()
        assert tables == ["embedding_index"]

        # 维度正确即可写入；写错维度会被 sqlite-vec 拒绝（见专用用例）
        session.execute(
            text("INSERT INTO embedding_index(chunk_id, embedding) VALUES (:id, :vec)"),
            {"id": "probe", "vec": to_vec0_literal(make_vector(0.0))},
        )


def test_save_to_index_and_search_returns_exact_match(session_factory):
    """写入向量后，用同一向量查询 top-1 应命中自身且距离为 0。"""
    chunk_id = seed_chunk(session_factory)

    with session_factory() as session:
        repository = EmbeddingRepository(session, embedding_dimension=DIMENSION)
        repository.save_to_index(chunk_id=chunk_id, vector=make_vector(0.1))
        session.commit()

    with session_factory() as session:
        results = EmbeddingRepository(
            session, embedding_dimension=DIMENSION
        ).search_similar(make_vector(0.1), top_k=1)

    assert len(results) == 1
    assert results[0][0] == chunk_id
    assert results[0][1] == pytest.approx(0.0)


def test_search_returns_results_ordered_by_distance(session_factory):
    """召回结果按距离升序排列。"""
    first = seed_chunk(session_factory, chunk_id="chunk-a")
    second = seed_chunk(session_factory, chunk_id="chunk-b")

    with session_factory() as session:
        repository = EmbeddingRepository(session, embedding_dimension=DIMENSION)
        repository.save_to_index(chunk_id=first, vector=make_vector(0.0))
        repository.save_to_index(chunk_id=second, vector=make_vector(1.0))
        session.commit()

    with session_factory() as session:
        results = EmbeddingRepository(
            session, embedding_dimension=DIMENSION
        ).search_similar(make_vector(0.0), top_k=2)

    assert [row[0] for row in results] == [first, second]
    assert results[0][1] <= results[1][1]


def test_search_top_k_larger_than_index_returns_all(session_factory):
    """top_k 大于实际记录数时返回全部，不报错。"""
    chunk_id = seed_chunk(session_factory)

    with session_factory() as session:
        EmbeddingRepository(session, embedding_dimension=DIMENSION).save_to_index(
            chunk_id=chunk_id, vector=make_vector(0.5)
        )
        session.commit()

    with session_factory() as session:
        results = EmbeddingRepository(
            session, embedding_dimension=DIMENSION
        ).search_similar(make_vector(0.5), top_k=5)

    assert len(results) == 1


def test_search_on_empty_index_returns_empty(session_factory):
    """空索引查询返回空列表。"""
    with session_factory() as session:
        results = EmbeddingRepository(
            session, embedding_dimension=DIMENSION
        ).search_similar(make_vector(0.5), top_k=5)

    assert results == []


def test_save_to_index_rejects_dimension_mismatch(session_factory):
    """维度不匹配的向量被拒绝写入，且索引中不出现该记录。"""
    chunk_id = seed_chunk(session_factory)

    with session_factory() as session:
        repository = EmbeddingRepository(session, embedding_dimension=DIMENSION)
        with pytest.raises(EmbeddingDimensionError):
            repository.save_to_index(chunk_id=chunk_id, vector=[0.1] * 128)

    with session_factory() as session:
        results = EmbeddingRepository(
            session, embedding_dimension=DIMENSION
        ).search_similar(make_vector(0.1), top_k=5)

    assert results == []


def test_save_to_index_rejects_missing_chunk(session_factory):
    """向不存在的 chunk 写索引被拒绝，且索引中不留下孤儿记录。"""
    with session_factory() as session:
        repository = EmbeddingRepository(session, embedding_dimension=DIMENSION)
        with pytest.raises(MissingChunkError):
            repository.save_to_index(chunk_id="missing-chunk", vector=make_vector(0.1))

    with session_factory() as session:
        results = EmbeddingRepository(
            session, embedding_dimension=DIMENSION
        ).search_similar(make_vector(0.1), top_k=5)

    assert results == []


def test_search_similar_rejects_dimension_mismatch(session_factory):
    """查询向量的维度与索引不一致时被拒绝，不返回误导性结果。"""
    with session_factory() as session:
        repository = EmbeddingRepository(session, embedding_dimension=DIMENSION)
        with pytest.raises(EmbeddingDimensionError):
            repository.search_similar([0.1] * 128, top_k=5)


def test_save_to_index_is_idempotent_per_chunk(session_factory):
    """同一个 chunk 重复写入索引后仍只有一条记录。"""
    chunk_id = seed_chunk(session_factory)

    with session_factory() as session:
        repository = EmbeddingRepository(session, embedding_dimension=DIMENSION)
        repository.save_to_index(chunk_id=chunk_id, vector=make_vector(0.1))
        repository.save_to_index(chunk_id=chunk_id, vector=make_vector(0.9))
        session.commit()

    with session_factory() as session:
        rows = session.execute(
            text("SELECT chunk_id FROM embedding_index WHERE chunk_id = :id"),
            {"id": chunk_id},
        ).scalars().all()
        results = EmbeddingRepository(
            session, embedding_dimension=DIMENSION
        ).search_similar(make_vector(0.9), top_k=5)

    assert rows == [chunk_id]
    assert results[0][0] == chunk_id
    assert results[0][1] == pytest.approx(0.0)


def test_reinitialize_keeps_existing_index(tmp_path):
    """重复初始化不丢失已写入的向量。"""
    data_dir = tmp_path / "data"
    first = initialize_database(data_dir=data_dir, embedding_dimension=DIMENSION)
    engine = create_database_engine(
        first.database_path,
        sqlite_vec_loader=load_sqlite_vec_extension,
    )
    factory = create_session_factory(engine)
    chunk_id = seed_chunk(factory)
    with factory() as session:
        EmbeddingRepository(session, embedding_dimension=DIMENSION).save_to_index(
            chunk_id=chunk_id, vector=make_vector(0.3)
        )
        session.commit()
    engine.dispose()

    second = initialize_database(data_dir=data_dir, embedding_dimension=DIMENSION)
    engine_again = create_database_engine(
        second.database_path,
        sqlite_vec_loader=load_sqlite_vec_extension,
    )
    with create_session_factory(engine_again)() as session:
        results = EmbeddingRepository(
            session, embedding_dimension=DIMENSION
        ).search_similar(make_vector(0.3), top_k=1)
    engine_again.dispose()

    assert results
    assert results[0][0] == chunk_id


def test_initialize_database_fails_when_loader_fails(tmp_path):
    """扩展加载失败时初始化失败，不报告成功。

    这是刻画既有行为的回归保护（US #19 的失败语义），不是本批新增的行为，
    因此它在 Red 阶段就会通过。
    """

    def failing_loader(connection):
        raise RuntimeError("sqlite-vec extension missing")

    with pytest.raises(SQLiteVecInitializationError):
        initialize_database(
            data_dir=tmp_path / "data",
            embedding_dimension=DIMENSION,
            sqlite_vec_loader=failing_loader,
        )


def test_search_similar_filters_hits_by_workspace(session_factory):
    """按 workspace 过滤要经 document_units → document_records 关联 —— chunks 表没有 workspace 列。"""
    in_scope = seed_chunk(session_factory, chunk_id="chunk-in", workspace_id="workspace_1")
    out_of_scope = seed_chunk(session_factory, chunk_id="chunk-out", workspace_id="workspace_2")

    with session_factory() as session:
        repository = EmbeddingRepository(session, embedding_dimension=DIMENSION)
        # 越界的那个离查询更近：不过滤时它必然排第一，过滤后必须消失
        repository.save_to_index(chunk_id=in_scope, vector=make_vector(0.5))
        repository.save_to_index(chunk_id=out_of_scope, vector=make_vector(0.0))
        session.commit()

    with session_factory() as session:
        results = EmbeddingRepository(session, embedding_dimension=DIMENSION).search_similar(
            make_vector(0.0), top_k=5, workspace_id="workspace_1"
        )

    assert [row[0] for row in results] == [in_scope]


def test_search_similar_without_workspace_returns_every_workspace(session_factory):
    """`workspace_id=None` 是**不过滤**（生产问答链路就这么调用），行为不能变。"""
    first = seed_chunk(session_factory, chunk_id="chunk-a", workspace_id="workspace_1")
    second = seed_chunk(session_factory, chunk_id="chunk-b", workspace_id="workspace_2")

    with session_factory() as session:
        repository = EmbeddingRepository(session, embedding_dimension=DIMENSION)
        repository.save_to_index(chunk_id=first, vector=make_vector(0.0))
        repository.save_to_index(chunk_id=second, vector=make_vector(1.0))
        session.commit()

    with session_factory() as session:
        results = EmbeddingRepository(session, embedding_dimension=DIMENSION).search_similar(
            make_vector(0.0), top_k=5
        )

    assert [row[0] for row in results] == [first, second]


def test_search_similar_filters_by_workspace_before_truncating_to_top_k(session_factory):
    """锁定 vec0 **子查询形式的过滤是 pre-filter**：`k` 作用在过滤**之后**。

    本 workspace 的片段全局排第 3 时，`top_k=1` 也能拿到它 —— 这就是检索适配器
    **不需要过采样**的依据（app/tools/adapters.py）。若把同一条件改写成 JOIN 或字面量 IN，
    行为会变成 post-filter（实测同样场景返回空），所以这条用例也守着"别把过滤写成 JOIN"。
    见 docs/specs/us-stage2-tools-wiring.md §4。
    """
    seed_chunk(session_factory, chunk_id="out-1", workspace_id="workspace_2")
    seed_chunk(session_factory, chunk_id="out-2", workspace_id="workspace_2")
    in_scope = seed_chunk(session_factory, chunk_id="in-1", workspace_id="workspace_1")

    with session_factory() as session:
        repository = EmbeddingRepository(session, embedding_dimension=DIMENSION)
        repository.save_to_index(chunk_id="out-1", vector=make_vector(0.0))
        repository.save_to_index(chunk_id="out-2", vector=make_vector(0.1))
        repository.save_to_index(chunk_id=in_scope, vector=make_vector(0.9))
        session.commit()

    with session_factory() as session:
        narrow = EmbeddingRepository(session, embedding_dimension=DIMENSION).search_similar(
            make_vector(0.0), top_k=1, workspace_id="workspace_1"
        )
        wide = EmbeddingRepository(session, embedding_dimension=DIMENSION).search_similar(
            make_vector(0.0), top_k=3, workspace_id="workspace_1"
        )

    assert [row[0] for row in narrow] == [in_scope]
    assert [row[0] for row in wide] == [in_scope]
