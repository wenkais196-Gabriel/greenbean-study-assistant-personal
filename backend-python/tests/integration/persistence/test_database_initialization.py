from contextlib import closing
import sqlite3

import sqlite_vec

import pytest

from app.db.init_db import (
    SQLiteVecInitializationError,
    initialize_database,
    load_sqlite_vec_extension,
)
from app.db.orm import create_database_engine, create_session_factory
from app.entities import DocumentRecord
from app.enums import DocumentFileType
from app.repositories.document_repository import DocumentRepository


def load_test_sqlite_vec(connection: sqlite3.Connection) -> None:
    """真加载 sqlite-vec（vec0 模块是建索引表的前提），但把 vec_version 覆盖为固定测试值。"""
    connection.enable_load_extension(True)
    try:
        sqlite_vec.load(connection)
    finally:
        connection.enable_load_extension(False)
    connection.create_function("vec_version", 0, lambda: "test-sqlite-vec")


def fail_to_load_sqlite_vec(connection: sqlite3.Connection) -> None:
    raise RuntimeError("sqlite-vec extension missing")


def test_default_sqlite_vec_loader_loads_extension_into_connection():
    """默认 loader 能把 sqlite-vec 真正加载进连接 —— 加载后可直接调用 vec_version()。

    原先这个用例用假 connection 断言"调用了 load_extension('sqlite_vec')"，
    那测的是实现细节，而且掩盖了该方法在实际环境下不工作的事实。
    """
    with closing(sqlite3.connect(":memory:")) as connection:
        load_sqlite_vec_extension(connection)

        version = connection.execute("SELECT vec_version()").fetchone()[0]

    assert isinstance(version, str)
    assert version.strip()


def test_first_start_creates_data_dir_and_sqlite_database(tmp_path):
    data_dir = tmp_path / "data"

    result = initialize_database(
        data_dir=data_dir,
        sqlite_vec_loader=load_test_sqlite_vec,
        embedding_dimension=8,
    )

    assert data_dir.exists()
    assert result.database_path.exists()
    assert result.database_path.parent == data_dir
    assert result.persistence_ready is True
    assert result.sqlite_vec_version == "test-sqlite-vec"


def test_repeated_start_keeps_database_initialization_idempotent(tmp_path):
    data_dir = tmp_path / "data"
    first_result = initialize_database(
        data_dir=data_dir,
        sqlite_vec_loader=load_test_sqlite_vec,
        embedding_dimension=8,
    )

    document = DocumentRecord(
        workspace_id="workspace_1",
        title="Syllabus",
        original_filename="syllabus.pdf",
        file_type=DocumentFileType.PDF,
        file_path="data/uploads/syllabus.pdf",
    )
    engine = create_database_engine(
        first_result.database_path,
        sqlite_vec_loader=load_test_sqlite_vec,
    )
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        DocumentRepository(session).save(document)
        session.commit()
    engine.dispose()

    second_result = initialize_database(
        data_dir=data_dir,
        sqlite_vec_loader=load_test_sqlite_vec,
        embedding_dimension=8,
    )

    engine = create_database_engine(
        second_result.database_path,
        sqlite_vec_loader=load_test_sqlite_vec,
    )
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        persisted = DocumentRepository(session).get_by_id(document.id)
    engine.dispose()

    assert second_result.persistence_ready is True
    assert persisted is not None
    assert persisted.id == document.id
    assert persisted.title == "Syllabus"


def test_successful_initialization_loads_sqlite_vec_and_creates_core_tables(tmp_path):
    result = initialize_database(
        data_dir=tmp_path / "data",
        sqlite_vec_loader=load_test_sqlite_vec,
        embedding_dimension=8,
    )

    with closing(sqlite3.connect(result.database_path)) as connection:
        table_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'virtual table')"
            ).fetchall()
        }

    assert result.sqlite_vec_version == "test-sqlite-vec"
    assert {
        "document_records",
        "document_units",
        "sections",
        "chunks",
        "analysis_results",
        "chat_sessions",
        "chat_messages",
        "embedding_vectors",
        "embedding_index",
    }.issubset(table_names)


def test_sqlite_vec_load_failure_fails_database_initialization(tmp_path):
    with pytest.raises(SQLiteVecInitializationError, match="sqlite-vec"):
        initialize_database(
            data_dir=tmp_path / "data",
            sqlite_vec_loader=fail_to_load_sqlite_vec,
            embedding_dimension=8,
        )


def test_sqlite_vec_health_check_failure_preserves_specific_error(tmp_path):
    with pytest.raises(SQLiteVecInitializationError, match="health check failed"):
        initialize_database(
            data_dir=tmp_path / "data",
            sqlite_vec_loader=lambda connection: None,
            embedding_dimension=8,
        )


def test_sqlite_vec_health_check_rejects_empty_version(tmp_path):
    def load_empty_version(connection: sqlite3.Connection) -> None:
        connection.create_function("vec_version", 0, lambda: None)

    with pytest.raises(SQLiteVecInitializationError, match="returned no version"):
        initialize_database(
            data_dir=tmp_path / "data",
            sqlite_vec_loader=load_empty_version,
            embedding_dimension=8,
        )
