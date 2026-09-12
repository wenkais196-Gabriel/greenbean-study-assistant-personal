from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select, text, update
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from app.db.models import ChunkModel, EmbeddingVectorModel
from app.repositories.sqlite_helpers import datetime_value, json_array, json_value


class EmbeddingDimensionError(ValueError):
    pass


class MissingChunkError(ValueError):
    pass


@dataclass(frozen=True)
class ChunkEmbedding:
    id: str
    chunk_id: str
    embedding_model: str
    vector_dimension: int
    vector: list[float]
    created_at: datetime


def _to_vec0_literal(vector: list[float]) -> str:
    """sqlite-vec 的 vec0 接受 JSON 数组形式的字面量。"""
    return "[" + ",".join(str(value) for value in vector) + "]"


class EmbeddingRepository:
    def __init__(self, session: Session, *, embedding_dimension: int) -> None:
        self.session = session
        self.embedding_dimension = embedding_dimension

    def save_for_chunk(
        self,
        *,
        chunk_id: str,
        embedding_model: str,
        vector: list[float],
    ) -> ChunkEmbedding:
        self._validate_dimension(vector)
        self.session.flush()
        if not self._chunk_exists(chunk_id):
            raise MissingChunkError(f"Chunk does not exist: {chunk_id}")

        embedding = ChunkEmbedding(
            id=str(uuid4()),
            chunk_id=chunk_id,
            embedding_model=embedding_model,
            vector_dimension=self.embedding_dimension,
            vector=vector,
            created_at=datetime.now(timezone.utc),
        )
        embedding_table = EmbeddingVectorModel.__table__
        statement = insert(embedding_table).values(
            id=embedding.id,
            chunk_id=embedding.chunk_id,
            embedding_model=embedding.embedding_model,
            vector_dimension=embedding.vector_dimension,
            vector_json=json_value(embedding.vector),
            created_at=datetime_value(embedding.created_at),
        )
        statement = statement.on_conflict_do_update(
            index_elements=[embedding_table.c.chunk_id],
            set_={
                "embedding_model": statement.excluded.embedding_model,
                "vector_dimension": statement.excluded.vector_dimension,
                "vector_json": statement.excluded.vector_json,
                "created_at": statement.excluded.created_at,
            },
        )
        self.session.execute(statement)
        self.session.execute(
            update(ChunkModel.__table__)
            .where(ChunkModel.__table__.c.id == embedding.chunk_id)
            .values(
                embedding_model=embedding.embedding_model,
                embedding_dimension=embedding.vector_dimension,
                embedding_created_at=datetime_value(embedding.created_at),
            )
        )
        return embedding

    def get_by_chunk_id(self, chunk_id: str) -> ChunkEmbedding | None:
        table = EmbeddingVectorModel.__table__
        row = self.session.execute(
            select(
                table.c.id,
                table.c.chunk_id,
                table.c.embedding_model,
                table.c.vector_dimension,
                table.c.vector_json,
                table.c.created_at,
            ).where(table.c.chunk_id == chunk_id)
        ).one_or_none()
        if row is None:
            return None
        return ChunkEmbedding(
            id=row[0],
            chunk_id=row[1],
            embedding_model=row[2],
            vector_dimension=row[3],
            vector=json_array(row[4]),
            created_at=datetime.fromisoformat(row[5]),
        )

    def save_to_index(self, *, chunk_id: str, vector: list[float]) -> None:
        """把向量写入 vec0 索引表（该表的维度在建库时已固定）。

        对同一个 chunk 重复写入是幂等的：vec0 不支持 INSERT OR REPLACE，故先删后插。
        """
        self._validate_dimension(vector)
        self.session.flush()
        if not self._chunk_exists(chunk_id):
            raise MissingChunkError(f"Chunk does not exist: {chunk_id}")

        self.session.execute(
            text("DELETE FROM embedding_index WHERE chunk_id = :chunk_id"),
            {"chunk_id": chunk_id},
        )
        self.session.execute(
            text(
                "INSERT INTO embedding_index(chunk_id, embedding) "
                "VALUES (:chunk_id, :embedding)"
            ),
            {"chunk_id": chunk_id, "embedding": _to_vec0_literal(vector)},
        )

    def search_similar(
        self,
        vector: list[float],
        *,
        top_k: int,
    ) -> list[tuple[str, float]]:
        """按距离升序返回 top_k 个最相近的 chunk。

        vec0 的 KNN 查询天然按距离升序返回，距离用其默认度量（L2 平方距离）。
        若日后要改成 cosine，需要在写入与查询前对向量做归一化。
        """
        self._validate_dimension(vector)
        rows = self.session.execute(
            text(
                "SELECT chunk_id, distance FROM embedding_index "
                "WHERE embedding MATCH :embedding AND k = :top_k"
            ),
            {"embedding": _to_vec0_literal(vector), "top_k": top_k},
        ).all()
        return [(row[0], row[1]) for row in rows]

    def _validate_dimension(self, vector: list[float]) -> None:
        if len(vector) != self.embedding_dimension:
            raise EmbeddingDimensionError(
                f"embedding vector dimension must be {self.embedding_dimension}, got {len(vector)}"
            )

    def _chunk_exists(self, chunk_id: str) -> bool:
        table = ChunkModel.__table__
        return (
            self.session.execute(
                select(table.c.id).where(table.c.id == chunk_id)
            ).scalar_one_or_none()
            is not None
        )
