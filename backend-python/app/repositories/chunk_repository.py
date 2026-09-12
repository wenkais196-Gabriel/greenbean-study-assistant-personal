from sqlalchemy.orm import Session

from app.db.models import ChunkModel
from app.entities import Chunk
from app.repositories.sqlite_helpers import datetime_value, json_object, json_value


class ChunkRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def save(self, chunk: Chunk) -> Chunk:
        model = self.session.get(ChunkModel, chunk.id)
        if model is None:
            model = ChunkModel(
                id=chunk.id,
                created_at=datetime_value(chunk.created_at),
            )
            self.session.add(model)
        model.document_unit_id = chunk.document_unit_id
        model.sequence_index = chunk.sequence_index
        model.text_content = chunk.text_content
        model.start_char = chunk.start_char
        model.end_char = chunk.end_char
        model.token_count = chunk.token_count
        model.metadata_json = json_value(chunk.metadata_json)
        model.chunker_name = chunk.chunker_name
        model.chunker_version = chunk.chunker_version
        model.embedding_model = chunk.embedding_model
        model.embedding_dimension = chunk.embedding_dimension
        model.embedding_created_at = (
            datetime_value(chunk.embedding_created_at) if chunk.embedding_created_at else None
        )
        return chunk

    def save_batch(self, chunks: list[Chunk]) -> list[Chunk]:
        """批量保存 Chunk；调用方负责 commit。返回保存后的列表。"""
        for chunk in chunks:
            self.save(chunk)
        return chunks

    def get_by_id(self, chunk_id: str) -> Chunk | None:
        model = self.session.get(ChunkModel, chunk_id)
        if model is None:
            return None
        return Chunk(
            id=model.id,
            document_unit_id=model.document_unit_id,
            sequence_index=model.sequence_index,
            text_content=model.text_content,
            start_char=model.start_char,
            end_char=model.end_char,
            token_count=model.token_count,
            metadata_json=json_object(model.metadata_json),
            chunker_name=model.chunker_name,
            chunker_version=model.chunker_version,
            embedding_model=model.embedding_model,
            embedding_dimension=model.embedding_dimension,
            embedding_created_at=model.embedding_created_at,
            created_at=model.created_at,
        )
