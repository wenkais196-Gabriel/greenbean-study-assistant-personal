"""
向量索引构建器：把 Chunk 的文本嵌入，并写入向量表与向量索引。

双写取舍见 planning/08 §2.1 与 docs/specs/us-stage1-embedding.md §9-A5：
- `embedding_vectors` 是权威记录（含 embedding_model 等元数据）
- `embedding_index` 是它的可检索副本（vec0 虚拟表）

**嵌入与写库拆成两步**（`embed_chunks` / `write_vectors`），不是为了好看：
SQLite 同一时刻只允许一个写者，落库事务一旦写下去，同一进程里别的连接就写不进 `ingest_jobs`，
进度回调会直接撞上 `database is locked`。把嵌入放到事务**之外**，进度才真的写得进库
（见 docs/specs/us-stage1-upload-async.md §3.2）。

分批嵌入也是同一个理由的延伸：一次 112 s 的黑盒对用户等于"卡死"，按批回调才有进度可言。
分批**不改变**嵌入结果 —— 每批独立送模型，模型对同一文本的输出与批的划分无关。
"""
from typing import Callable

from app.config.settings import EMBEDDING_BATCH_SIZE, EMBEDDING_MODEL
from app.entities import Chunk
from app.repositories.embedding_repository import EmbeddingRepository
from app.services.embedding_service import EmbeddingService

ProgressCallback = Callable[[int, int], None]
"""`on_progress(已处理条数, 总条数)` —— 每批结束回调一次。"""


class VectorIndexBuilder:
    def __init__(
        self,
        embedding_service: EmbeddingService,
        *,
        embedding_model: str = EMBEDDING_MODEL,
        batch_size: int = EMBEDDING_BATCH_SIZE,
    ) -> None:
        self.embedding_service = embedding_service
        self.embedding_model = embedding_model
        self.batch_size = batch_size

    def embed_chunks(
        self,
        chunks: list[Chunk],
        *,
        on_progress: ProgressCallback | None = None,
    ) -> list[list[float]]:
        """分批嵌入，返回与 `chunks` 等长的向量列表。

        **纯计算，不碰数据库** —— 调用方可以在事务之外调用它，进度回调因此不会被写锁挡住。
        空列表返回空结果，且不加载模型。
        """
        if not chunks:
            return []

        total = len(chunks)
        vectors: list[list[float]] = []
        processed = 0
        for start in range(0, total, self.batch_size):
            batch = chunks[start : start + self.batch_size]
            vectors.extend(
                self.embedding_service.embed_texts(
                    [chunk.text_content for chunk in batch]
                )
            )
            processed += len(batch)
            if on_progress is not None:
                on_progress(processed, total)
        return vectors

    def write_vectors(
        self,
        repository: EmbeddingRepository,
        chunks: list[Chunk],
        vectors: list[list[float]],
    ) -> None:
        """把向量双写到权威表与索引表；调用方负责 commit。"""
        for chunk, vector in zip(chunks, vectors):
            # 先写权威记录，再写索引：索引若丢失，可由权威记录重建
            repository.save_for_chunk(
                chunk_id=chunk.id,
                embedding_model=self.embedding_model,
                vector=vector,
            )
            repository.save_to_index(chunk_id=chunk.id, vector=vector)

    def build_for_chunks(
        self,
        repository: EmbeddingRepository,
        chunks: list[Chunk],
        *,
        on_progress: ProgressCallback | None = None,
    ) -> int:
        """嵌入 + 双写一步到位，返回处理的条数。

        空列表直接返回 0（不加载模型）。调用方负责 commit。
        `on_progress` 是**可选观测点**：不传它，行为与从前完全一致。

        ⚠️ 调用方若同时要写别的表（例如上传任务的进度），请改用
        `embed_chunks` + `write_vectors`，把嵌入挪到事务之外 —— 否则会撞 SQLite 写锁。
        """
        if not chunks:
            return 0

        vectors = self.embed_chunks(chunks, on_progress=on_progress)
        self.write_vectors(repository, chunks, vectors)
        return len(chunks)
