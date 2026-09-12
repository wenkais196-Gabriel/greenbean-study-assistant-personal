"""
向量索引构建器：把 Chunk 的文本嵌入，并写入向量表与向量索引。

双写取舍见 planning/08 §2.1 与 docs/specs/us-stage1-embedding.md §9-A5：
- `embedding_vectors` 是权威记录（含 embedding_model 等元数据）
- `embedding_index` 是它的可检索副本（vec0 虚拟表）
"""
from app.config.settings import EMBEDDING_MODEL
from app.entities import Chunk
from app.repositories.embedding_repository import EmbeddingRepository
from app.services.embedding_service import EmbeddingService


class VectorIndexBuilder:
    def __init__(
        self,
        embedding_service: EmbeddingService,
        *,
        embedding_model: str = EMBEDDING_MODEL,
    ) -> None:
        self.embedding_service = embedding_service
        self.embedding_model = embedding_model

    def build_for_chunks(
        self,
        repository: EmbeddingRepository,
        chunks: list[Chunk],
    ) -> int:
        """为一批 Chunk 构建索引，返回处理的条数。

        空列表直接返回 0（不加载模型）。调用方负责 commit。
        """
        if not chunks:
            return 0

        vectors = self.embedding_service.embed_texts(
            [chunk.text_content for chunk in chunks]
        )
        for chunk, vector in zip(chunks, vectors):
            # 先写权威记录，再写索引：索引若丢失，可由权威记录重建
            repository.save_for_chunk(
                chunk_id=chunk.id,
                embedding_model=self.embedding_model,
                vector=vector,
            )
            repository.save_to_index(chunk_id=chunk.id, vector=vector)
        return len(chunks)
