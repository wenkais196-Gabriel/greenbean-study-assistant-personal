"""
运行时装配（app/db/runtime）：建库、缓存、懒加载 —— 真 sqlite-vec、临时目录。

顺带覆盖 `initialize_database` 的一个防御分支：`embedding_index` 这个名字被**普通表**占用
（不是 vec0）时，解析不到维度就早返回，而不是抛错。
"""
import sqlite3

import pytest
from sqlalchemy import text

from app.db import runtime
from app.db.init_db import initialize_database, load_sqlite_vec_extension

pytestmark = [pytest.mark.integration]

DIMENSION = 8


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path, monkeypatch):
    """把 runtime 指向临时目录，并清掉 lru_cache，避免测试之间互相污染。"""
    monkeypatch.setattr(runtime, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(runtime, "DATABASE_NAME", "runtime.sqlite3")
    monkeypatch.setattr(runtime, "EMBEDDING_DIMENSION", DIMENSION)
    runtime.get_session_factory.cache_clear()
    try:
        yield
    finally:
        runtime.get_session_factory.cache_clear()


def test_get_session_factory_creates_database_and_caches_it(tmp_path):
    factory = runtime.get_session_factory()

    assert (tmp_path / "runtime.sqlite3").exists()
    assert runtime.get_session_factory() is factory, "重复调用应命中缓存"

    with factory() as session:
        assert session.execute(text("SELECT 1")).scalar() == 1


def test_lazy_session_factory_defers_database_creation(tmp_path):
    factory = runtime.lazy_session_factory()

    assert not (tmp_path / "runtime.sqlite3").exists(), "构造时不该建库"

    with factory() as session:
        assert session is not None

    assert (tmp_path / "runtime.sqlite3").exists(), "第一次开会话时才建库"


def test_initialize_database_tolerates_non_vec0_embedding_index_table(tmp_path):
    """`embedding_index` 被普通表占用时不该崩：解析不到维度就早返回。"""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    with sqlite3.connect(data_dir / "odd.sqlite3") as connection:
        connection.execute("CREATE TABLE embedding_index (chunk_id TEXT PRIMARY KEY)")
        connection.commit()

    result = initialize_database(
        data_dir=data_dir,
        database_name="odd.sqlite3",
        embedding_dimension=DIMENSION,
        sqlite_vec_loader=load_sqlite_vec_extension,
    )

    assert result.persistence_ready is True
