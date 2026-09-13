from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
import re
import sqlite3
from typing import Callable

import sqlite_vec


SQLiteVecLoader = Callable[[sqlite3.Connection], None]


class SQLiteVecInitializationError(RuntimeError):
    """Raised when sqlite-vec cannot be loaded or checked."""


@dataclass(frozen=True)
class DatabaseInitializationResult:
    database_path: Path
    persistence_ready: bool
    sqlite_vec_version: str


def load_sqlite_vec_extension(connection: sqlite3.Connection) -> None:
    """加载 sqlite-vec 扩展。

    改用官方 Python 包的 `sqlite_vec.load()`，而不是 sqlite3 的 `load_extension("sqlite_vec")`：
    后者要求动态库搜索路径中存在同名共享库，在 Windows + Python 3.12 上不成立
    （实测报 "找不到指定的模块"）。

    仍需保留 enable/disable 包装 —— 未启用扩展加载时 `sqlite_vec.load()` 会报 "not authorized"。
    """
    connection.enable_load_extension(True)
    try:
        sqlite_vec.load(connection)
    finally:
        connection.enable_load_extension(False)


def initialize_database(
    *,
    data_dir: str | Path = Path("data"),
    database_name: str = "greenbean-study-assistant.sqlite3",
    sqlite_vec_loader: SQLiteVecLoader = load_sqlite_vec_extension,
    embedding_dimension: int,
) -> DatabaseInitializationResult:
    data_path = Path(data_dir)
    data_path.mkdir(parents=True, exist_ok=True)
    database_path = data_path / database_name

    try:
        with closing(sqlite3.connect(database_path)) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            sqlite_vec_loader(connection)
            sqlite_vec_version = _check_sqlite_vec(connection)
            _create_schema(connection, embedding_dimension)
            connection.commit()
    except SQLiteVecInitializationError:
        raise
    except Exception as exc:
        raise SQLiteVecInitializationError(f"sqlite-vec initialization failed: {exc}") from exc

    return DatabaseInitializationResult(
        database_path=database_path,
        persistence_ready=True,
        sqlite_vec_version=sqlite_vec_version,
    )


# 从 vec0 的建表 SQL 里取维度，形如：embedding float[1024]
_VEC0_DIMENSION_PATTERN = re.compile(r"embedding\s+float\[(\d+)\]", re.IGNORECASE)


def _ensure_vector_index(connection: sqlite3.Connection, embedding_dimension: int) -> None:
    """建向量索引表；若已存在但**维度与当前配置不一致**，抛明确错误。

    vec0 的维度在建表时固定、不能原地改，而换 embedding 模型会改变维度。
    这里选择"早失败 + 说清怎么修"，而不是让后续写入抛出难懂的底层错误：
    `embedding_index` 是可以从 `embedding_vectors` 重建的副本，重建后重跑嵌入即可。
    """
    connection.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS embedding_index USING vec0("
        f"chunk_id TEXT PRIMARY KEY, embedding float[{int(embedding_dimension)}])"
    )

    row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'embedding_index'"
    ).fetchone()
    match = _VEC0_DIMENSION_PATTERN.search(row[0]) if row and row[0] else None
    if match is None:
        return

    existing = int(match.group(1))
    if existing != int(embedding_dimension):
        raise SQLiteVecInitializationError(
            f"向量索引已按 {existing} 维建立，与当前配置的 {int(embedding_dimension)} 维不一致："
            "换了 embedding 模型就必须重建索引 —— 删除 embedding_index 后重新初始化，"
            "并重新为全部 chunk 生成向量（embedding_vectors 是权威数据，索引可据此重建）"
        )


def _ensure_analysis_result_summary(connection: sqlite3.Connection) -> None:
    """给旧库的 `analysis_results` 补上 `summary` 列（幂等）。

    `CREATE TABLE IF NOT EXISTS` 不会给**已存在**的表加列，所以旧库要显式 ALTER；
    而 SQLite 的 `ADD COLUMN` 不支持 `IF NOT EXISTS`，因此先查 `PRAGMA table_info`
    —— 与 `_ensure_vector_index` 同样的"先看现状、再补齐"思路。
    """
    columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info(analysis_results)").fetchall()
    }
    if "summary" not in columns:
        connection.execute("ALTER TABLE analysis_results ADD COLUMN summary TEXT")


def _check_sqlite_vec(connection: sqlite3.Connection) -> str:
    try:
        row = connection.execute("SELECT vec_version()").fetchone()
    except sqlite3.Error as exc:
        raise SQLiteVecInitializationError(f"sqlite-vec health check failed: {exc}") from exc

    if row is None or not row[0]:
        raise SQLiteVecInitializationError("sqlite-vec health check failed: vec_version() returned no version")
    return str(row[0])


def _create_schema(connection: sqlite3.Connection, embedding_dimension: int) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS document_records (
            id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            title TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            file_type TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_hash TEXT,
            status TEXT NOT NULL,
            page_count INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS document_units (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            sequence_index INTEGER NOT NULL,
            text_content TEXT NOT NULL,
            page_number INTEGER,
            start_char INTEGER,
            end_char INTEGER,
            token_count INTEGER,
            metadata_json TEXT,
            raw_content_json TEXT,
            parser_name TEXT,
            parser_version TEXT,
            external_id TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (document_id) REFERENCES document_records(id),
            UNIQUE (document_id, sequence_index)
        );

        CREATE TABLE IF NOT EXISTS sections (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            parent_section_id TEXT,
            title TEXT NOT NULL,
            level INTEGER NOT NULL,
            order_index INTEGER NOT NULL,
            start_page INTEGER,
            end_page INTEGER,
            summary TEXT,
            metadata_json TEXT,
            parser_name TEXT,
            parser_version TEXT,
            external_id TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (document_id) REFERENCES document_records(id),
            FOREIGN KEY (parent_section_id) REFERENCES sections(id)
        );

        CREATE TABLE IF NOT EXISTS chunks (
            id TEXT PRIMARY KEY,
            document_unit_id TEXT NOT NULL,
            sequence_index INTEGER NOT NULL,
            text_content TEXT NOT NULL,
            start_char INTEGER,
            end_char INTEGER,
            token_count INTEGER,
            metadata_json TEXT,
            chunker_name TEXT,
            chunker_version TEXT,
            embedding_model TEXT,
            embedding_dimension INTEGER,
            embedding_created_at TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (document_unit_id) REFERENCES document_units(id),
            UNIQUE (document_unit_id, sequence_index)
        );

        CREATE TABLE IF NOT EXISTS analysis_results (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            section_id TEXT,
            analysis_type TEXT NOT NULL,
            language TEXT NOT NULL,
            content_markdown TEXT NOT NULL,
            summary TEXT,
            content_json TEXT,
            model_name TEXT,
            prompt_version TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (document_id) REFERENCES document_records(id),
            FOREIGN KEY (section_id) REFERENCES sections(id)
        );

        CREATE TABLE IF NOT EXISTS chat_sessions (
            id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            document_id TEXT,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (document_id) REFERENCES document_records(id)
        );

        CREATE TABLE IF NOT EXISTS chat_messages (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            source_context_json TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
        );

        CREATE TABLE IF NOT EXISTS embedding_vectors (
            id TEXT PRIMARY KEY,
            chunk_id TEXT NOT NULL UNIQUE,
            embedding_model TEXT NOT NULL,
            vector_dimension INTEGER NOT NULL,
            vector_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (chunk_id) REFERENCES chunks(id)
        );

        CREATE TABLE IF NOT EXISTS provider_configs (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            api_mode TEXT NOT NULL,
            api_key TEXT NOT NULL,
            api_host TEXT NOT NULL,
            api_path TEXT NOT NULL,
            model_id TEXT NOT NULL,
            display_name TEXT NOT NULL,
            context_window INTEGER NOT NULL,
            max_output_tokens INTEGER NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS ingest_jobs (
            id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            workspace_id TEXT NOT NULL,
            status TEXT NOT NULL,
            stage TEXT,
            progress REAL NOT NULL DEFAULT 0,
            error TEXT,
            result_json TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS agent_traces (
            id TEXT PRIMARY KEY,
            trace_id TEXT NOT NULL,
            parent_id TEXT,
            span_name TEXT NOT NULL,
            status TEXT NOT NULL,
            duration_ms REAL NOT NULL,
            attributes_json TEXT,
            error TEXT,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_agent_traces_trace_id ON agent_traces (trace_id);

        CREATE TABLE IF NOT EXISTS app_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )
    # 向量索引（sqlite-vec 的 vec0 虚拟表）。
    # ⚠️ 维度在建表时固定，sqlite-vec 不支持就地改维度：换 embedding 模型必须重建该表。
    # 它会创建若干伴生表（embedding_index_info / _chunks / _rowids / _vector_chunks00），
    # 这是 sqlite-vec 的正常行为。
    _ensure_vector_index(connection, embedding_dimension)
    # 旧库补列（纯新增字段，不重建表）：CREATE TABLE IF NOT EXISTS 不会给已存在的表加列。
    _ensure_analysis_result_summary(connection)
    connection.execute(
        """
        INSERT INTO app_metadata(key, value)
        VALUES('embedding_dimension', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (str(embedding_dimension),),
    )
