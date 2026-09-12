import sqlite3

import sqlite_vec

import pytest

from app.db.init_db import initialize_database
from app.db.orm import create_database_engine, create_session_factory
from app.db.unit_of_work import SqlAlchemyUnitOfWork
from app.entities import Chunk, DocumentRecord, DocumentUnit
from app.enums import AnalysisType, DocumentFileType, MessageRole
from app.repositories.analysis_result_repository import AnalysisResultRepository
from app.repositories.chat_message_repository import ChatMessageRepository
from app.repositories.chat_session_repository import ChatSessionRepository
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.document_unit_repository import DocumentUnitRepository
from app.repositories.embedding_repository import EmbeddingRepository
from app.repositories.section_repository import SectionRepository
from app.repositories.sqlite_helpers import enum_value


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


def make_document(title: str = "Course Deck") -> DocumentRecord:
    return DocumentRecord(
        workspace_id="workspace_1",
        title=title,
        original_filename="course.pptx",
        file_type=DocumentFileType.PPTX,
        file_path="data/uploads/course.pptx",
    )


def save_chunk_source(session):
    document = make_document()
    unit = DocumentUnit(
        document_id=document.id,
        sequence_index=0,
        text_content="Source unit",
    )
    chunk = Chunk(
        document_unit_id=unit.id,
        sequence_index=0,
        text_content="Source chunk",
    )
    DocumentRepository(session).save(document)
    DocumentUnitRepository(session).save(unit)
    ChunkRepository(session).save(chunk)
    return chunk


def test_repository_does_not_commit_its_own_changes(session_factory):
    document = make_document()

    with session_factory() as session:
        DocumentRepository(session).save(document)
        session.rollback()

    with session_factory() as session:
        assert DocumentRepository(session).get_by_id(document.id) is None


def test_unit_of_work_commits_repository_changes(session_factory):
    document = make_document()

    with SqlAlchemyUnitOfWork(session_factory) as unit_of_work:
        DocumentRepository(unit_of_work.session).save(document)
        unit_of_work.commit()

    with session_factory() as session:
        persisted = DocumentRepository(session).get_by_id(document.id)

    assert persisted is not None
    assert persisted.title == document.title


def test_unit_of_work_rolls_back_when_operation_fails(session_factory):
    document = make_document()

    with pytest.raises(RuntimeError, match="stop transaction"):
        with SqlAlchemyUnitOfWork(session_factory) as unit_of_work:
            DocumentRepository(unit_of_work.session).save(document)
            raise RuntimeError("stop transaction")

    with session_factory() as session:
        assert DocumentRepository(session).get_by_id(document.id) is None


def test_unit_of_work_supports_explicit_rollback(session_factory):
    document = make_document()

    with SqlAlchemyUnitOfWork(session_factory) as unit_of_work:
        DocumentRepository(unit_of_work.session).save(document)
        unit_of_work.rollback()

    with session_factory() as session:
        assert DocumentRepository(session).get_by_id(document.id) is None


def test_engine_initializes_foreign_keys_and_sqlite_vec_on_every_connection(tmp_path):
    result = initialize_database(
        data_dir=tmp_path / "data",
        sqlite_vec_loader=load_test_sqlite_vec,
        embedding_dimension=8,
    )
    engine = create_database_engine(
        result.database_path,
        sqlite_vec_loader=load_test_sqlite_vec,
    )

    try:
        with engine.connect() as connection:
            foreign_keys = connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one()
            sqlite_vec_version = connection.exec_driver_sql("SELECT vec_version()").scalar_one()
    finally:
        engine.dispose()

    assert foreign_keys == 1
    assert sqlite_vec_version == "test-sqlite-vec"


def test_core_embedding_changes_roll_back_with_the_session(session_factory):
    with session_factory() as session:
        chunk = save_chunk_source(session)
        session.commit()

    with session_factory() as session:
        EmbeddingRepository(session, embedding_dimension=2).save_for_chunk(
            chunk_id=chunk.id,
            embedding_model="test-model",
            vector=[0.1, 0.2],
        )
        session.rollback()

    with session_factory() as session:
        embedding = EmbeddingRepository(session, embedding_dimension=2).get_by_chunk_id(chunk.id)
        persisted_chunk = ChunkRepository(session).get_by_id(chunk.id)

    assert embedding is None
    assert persisted_chunk.embedding_model is None


def test_core_embedding_update_is_visible_to_orm_in_the_same_session(session_factory):
    with session_factory() as session:
        chunk = save_chunk_source(session)
        EmbeddingRepository(session, embedding_dimension=2).save_for_chunk(
            chunk_id=chunk.id,
            embedding_model="test-model",
            vector=[0.1, 0.2],
        )

        updated_chunk = ChunkRepository(session).get_by_id(chunk.id)

    assert updated_chunk.embedding_model == "test-model"
    assert updated_chunk.embedding_dimension == 2


def test_repositories_return_none_for_missing_records(session_factory):
    with session_factory() as session:
        assert AnalysisResultRepository(session).get_by_id("missing") is None
        assert ChatMessageRepository(session).get_by_id("missing") is None
        assert ChatSessionRepository(session).get_by_id("missing") is None
        assert ChunkRepository(session).get_by_id("missing") is None
        assert DocumentUnitRepository(session).get_by_id("missing") is None
        assert SectionRepository(session).get_by_id("missing") is None


def test_enum_value_keeps_plain_values_unchanged():
    assert enum_value("plain-value") == "plain-value"
    assert enum_value(DocumentFileType.PDF) == "pdf"
    assert enum_value(AnalysisType.FULL_DOCUMENT) == "full_document"
    assert enum_value(MessageRole.USER) == "user"
