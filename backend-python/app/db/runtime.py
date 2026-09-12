"""
生产数据库的运行时装配：建库（含 vec0 向量索引）→ engine → session_factory。

进程内**懒加载单例**：第一次真正取会话时才建库，避免"只是构造一个 service"就写磁盘。
测试**不要**用这里 —— 测试各自建临时库，再把 session_factory 注入被测对象。
"""
from functools import lru_cache

from sqlalchemy.orm import Session

from app.config.settings import DATA_DIR, DATABASE_NAME, EMBEDDING_DIMENSION
from app.db.init_db import initialize_database, load_sqlite_vec_extension
from app.db.orm import SessionFactory, create_database_engine, create_session_factory


@lru_cache(maxsize=1)
def get_session_factory() -> SessionFactory:
    """按 settings 建库并返回 session_factory（进程内只做一次）。

    ⚠️ vec0 向量表的维度在建库时固定：换 embedding 模型必须重建索引 ——
    `initialize_database` 会在维度不一致时明确报错。
    """
    result = initialize_database(
        data_dir=DATA_DIR,
        database_name=DATABASE_NAME,
        embedding_dimension=EMBEDDING_DIMENSION,
        sqlite_vec_loader=load_sqlite_vec_extension,
    )
    engine = create_database_engine(
        result.database_path,
        sqlite_vec_loader=load_sqlite_vec_extension,
    )
    return create_session_factory(engine)


def lazy_session_factory() -> SessionFactory:
    """返回一个"用到才建库"的 SessionFactory。

    给在请求构造期就实例化的 service 用：构造时不碰磁盘，第一次开会话时才触发
    `get_session_factory()`（这样 `get_ingest_service()` 这类依赖注入不会有副作用）。
    """

    def _factory() -> Session:
        return get_session_factory()()

    return _factory
