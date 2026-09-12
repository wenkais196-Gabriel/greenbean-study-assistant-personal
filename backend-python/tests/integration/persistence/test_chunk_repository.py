"""
ChunkRepository 批量持久化集成测试。

对应规格：docs/specs/us-stage1-chunking.md（AC7）
"""
import sqlite3

import sqlite_vec

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.init_db import initialize_database
from app.db.models import ChunkModel
from app.db.orm import create_database_engine, create_session_factory
from app.entities import Chunk, DocumentRecord, DocumentUnit
from app.enums import DocumentFileType
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.document_unit_repository import DocumentUnitRepository


def load_test_sqlite_vec(connection: sqlite3.Connection) -> None:
    """真加载 sqlite-vec（vec0 模块是建索引表的前提），但把 vec_version 覆盖为固定测试值。"""
    connection.enable_load_extension(True)
    try:
        sqlite_vec.load(connection)
    finally:
        connection.enable_load_extension(False)
    connection.create_function("vec_version", 0, lambda: "test-sqlite-vec")


@pytest.fixture
def session_factory(tmp_path):
    result = initialize_database(
        data_dir=tmp_path / "data",
        sqlite_vec_loader=load_test_sqlite_vec,
        embedding_dimension=8,
    )
    engine = create_database_engine(
        result.database_path,
        sqlite_vec_loader=load_test_sqlite_vec,
    )
    yield create_session_factory(engine)
    engine.dispose()


def seed_document_unit(session_factory):
    """写入一个 DocumentRecord + DocumentUnit，返回该 unit。"""
    document = DocumentRecord(
        workspace_id="workspace_1",
        title="Cours d'algorithmique",
        original_filename="cours.pdf",
        file_type=DocumentFileType.PDF,
        file_path="data/uploads/cours.pdf",
        page_count=3,
    )
    unit = DocumentUnit(
        document_id=document.id,
        sequence_index=0,
        text_content="Le polymorphisme est un concept fondamental.",
        page_number=1,
    )
    with session_factory() as session:
        DocumentRepository(session).save(document)
        DocumentUnitRepository(session).save(unit)
        session.commit()
    return unit


def test_save_batch_persists_all_chunks_in_order(session_factory):
    """批量保存的 Chunk 全部落库，且按 sequence_index 读回的顺序与写入一致。"""
    unit = seed_document_unit(session_factory)
    chunks = [
        Chunk(document_unit_id=unit.id, sequence_index=index, text_content=f"Fragment {index}")
        for index in range(3)
    ]

    with session_factory() as session:
        ChunkRepository(session).save_batch(chunks)
        session.commit()

    with session_factory() as session:
        persisted = ChunkRepository(session).get_by_id(chunks[1].id)
        assert persisted.document_unit_id == unit.id
        assert persisted.text_content == "Fragment 1"

    with session_factory() as session:
        ordered = session.execute(
            select(ChunkModel.sequence_index)
            .where(ChunkModel.document_unit_id == unit.id)
            .order_by(ChunkModel.sequence_index)
        ).scalars().all()

    assert list(ordered) == [0, 1, 2]


def test_save_batch_rejects_duplicate_sequence_index(session_factory):
    """同一单元内重复的 sequence_index 被数据库唯一约束拒绝，不静默覆盖。"""
    unit = seed_document_unit(session_factory)

    with session_factory() as session:
        ChunkRepository(session).save_batch(
            [Chunk(document_unit_id=unit.id, sequence_index=0, text_content="Premier fragment")]
        )
        session.commit()

    with session_factory() as session:
        ChunkRepository(session).save_batch(
            [Chunk(document_unit_id=unit.id, sequence_index=0, text_content="Fragment dupliqué")]
        )
        with pytest.raises(IntegrityError):
            session.commit()
