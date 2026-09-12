"""
文档摄取服务：解析 → 实体构建 → 切块 → 嵌入 → 落库。

两种运行模式（沿用上游"渐进式交付"的分阶段思路）：

- **完整摄取**：注入了 `session_factory` 时，在**同一事务**里写入
  `document_records` / `document_units` / `chunks` / `embedding_vectors` / `embedding_index`，
  完成后数据即可被检索链路（Retriever / ContextBuilder）直接使用；
- **只解析**：未注入时只解析并构造实体（预览用，不碰数据库）。

⚠️ 嵌入在 CPU 上不是即时操作（e5-large 实测约 200 ms/片段，290 页资料约 112 s）：
调用方应把它放进线程池执行，别阻塞事件循环（见 `document_controller` 与 `IngestJobService`）。

⚠️ **嵌入必须发生在任何写库之前**，这是正确性而不是风格问题：SQLite 同一时刻只允许一个写者，
落库事务一旦写下去，上传任务的进度写（另一个连接）就会撞上 `database is locked`。
所以流水线是"先算完再写"，进度回调落在无锁的事务之外
（见 docs/specs/us-stage1-upload-async.md §3.2）。

`on_progress` 与 `trace_recorder` 都是**可选观测点**：不传它们，本服务的行为与从前完全一致。
trace 的 span 同样只在事务之外写（见 docs/specs/us-stage1-trace.md §3.4）。
"""
import os
import time
from contextlib import nullcontext
from typing import Callable, ContextManager

from app.config.settings import EMBEDDING_DIMENSION, EMBEDDING_MODEL
from app.db.orm import SessionFactory
from app.entities import Chunk, DocumentRecord, DocumentUnit
from app.enums.document_file_type import DocumentFileType
from app.enums.document_status import DocumentStatus
from app.enums.ingest_stage import IngestStage
from app.enums.trace_status import TraceStatus
from app.parsers.parser_factory import ParserFactory
from app.rag.vector_index_builder import VectorIndexBuilder
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.document_unit_repository import DocumentUnitRepository
from app.repositories.embedding_repository import EmbeddingRepository
from app.services.chunk_service import ChunkService
from app.services.embedding_service import EmbeddingService
from app.services.trace_recorder import TraceRecorder, elapsed_ms
from app.utils.trace_context import bind_trace, current_trace_id, reset_trace

# source_type → DocumentFileType 映射常量
SOURCE_TYPE_TO_FILE_TYPE: dict[str, DocumentFileType] = {
    "pdf": DocumentFileType.PDF,
    "word": DocumentFileType.DOCX,
    "ppt": DocumentFileType.PPTX,
    "image": DocumentFileType.IMAGE,
    "text": DocumentFileType.TEXT,
}

ProgressCallback = Callable[[IngestStage, float], None]
"""`on_progress(阶段, 该阶段完成度 0~1)`；整体进度的加权换算由调用方决定。"""

# span 名称：成功与失败两条分支**必须同名**，否则同一次摄取会在两个分支下变成两类数据
SPAN_INGEST_DOCUMENT = "ingest.document"


class DocumentIngestService:
    """安全文档摄取流水线：解析 → 实体构建 → 切块 → 嵌入 → （可选）落库。"""

    def __init__(
        self,
        *,
        session_factory: SessionFactory | None = None,
        chunk_service: ChunkService | None = None,
        embedding_service: EmbeddingService | None = None,
        embedding_model: str = EMBEDDING_MODEL,
        embedding_dimension: int = EMBEDDING_DIMENSION,
        trace_recorder: TraceRecorder | None = None,
    ) -> None:
        """
        :param session_factory: 会话工厂；**注入即开启完整摄取**（切块 + 嵌入 + 落库），
            不注入则只做解析与实体构建
        :param chunk_service: 切块服务，默认用生产配置的 `ChunkService()`
        :param embedding_service: 嵌入服务，默认懒加载生产配置（**测试请注入假模型**）
        :param embedding_model: 写入 `embedding_vectors.embedding_model` 供追溯
        :param embedding_dimension: 向量维度，必须与建库时的 vec0 维度一致
        :param trace_recorder: 结构化 trace 记录器；**默认不记录**，由调用方显式注入。
            这里刻意不 fallback 到生产单例：多一个默认值，就会让既有构造点（尤其测试）
            悄悄开始往生产库写 span —— 这个坑在实现本批时真的踩到了。
        """
        self.session_factory = session_factory
        self.chunk_service = chunk_service or ChunkService()
        self.embedding_service = embedding_service
        self.embedding_model = embedding_model
        self.embedding_dimension = embedding_dimension
        self.trace_recorder = trace_recorder

    def ingest_document(
        self,
        filename: str,
        file_content: bytes,
        *,
        workspace_id: str = "",
        title: str | None = None,
        file_path: str = "",
        file_hash: str | None = None,
        on_progress: ProgressCallback | None = None,
        job_id: str | None = None,
    ) -> dict:
        """
        贯穿整个文件流的摄取流水线。

        :param filename: 文件名（含扩展名）
        :param file_content: 文件二进制数据
        :param workspace_id: 所属工作区 ID
        :param title: 文档标题，不传则从文件名推导
        :param file_path: 原始文件在本地 uploads 目录下的路径
        :param file_hash: 原始文件哈希值
        :param on_progress: 阶段进度回调（可选），供上传进度反馈消费
        :param job_id: 上传任务 ID（可选），写进 trace 便于与 `ingest_jobs` 对照
        :return: 解析结果字典，含 document_record / document_units / chunks_created / elapsed_seconds
        """
        token = bind_trace(current_trace_id())
        started = time.perf_counter()
        try:
            result = self._ingest(
                filename,
                file_content,
                workspace_id=workspace_id,
                title=title,
                file_path=file_path,
                file_hash=file_hash,
                on_progress=on_progress,
            )
        except Exception as exc:
            self._record(
                SPAN_INGEST_DOCUMENT,
                elapsed_ms(started),
                status=TraceStatus.ERROR,
                error=f"{type(exc).__name__}: {exc}",
                **{
                    "greenbean.ingest.filename": filename,
                    "greenbean.ingest.job_id": job_id,
                },
            )
            raise
        else:
            self._record(
                SPAN_INGEST_DOCUMENT,
                elapsed_ms(started),
                **{
                    "greenbean.ingest.filename": filename,
                    "greenbean.ingest.pages": result["total_pages"],
                    "greenbean.ingest.chunks_created": result["chunks_created"],
                    "greenbean.ingest.elapsed_seconds": result["elapsed_seconds"],
                    "greenbean.ingest.job_id": job_id,
                },
            )
            return result
        finally:
            reset_trace(token)

    def _ingest(
        self,
        filename: str,
        file_content: bytes,
        *,
        workspace_id: str,
        title: str | None,
        file_path: str,
        file_hash: str | None,
        on_progress: ProgressCallback | None,
    ) -> dict:
        """摄取主体（由 `ingest_document` 包上 trace 与 trace 上下文）。"""
        started = time.perf_counter()

        # ---- Step 1: 通过工厂匹配解析器并提取 PageIndex 原始单页文本 ----
        self._report(on_progress, IngestStage.PARSING, 0.0)
        with self._stage_span("ingest.parsing"):
            parser = ParserFactory.get_parser(filename)
            parsed_pages = parser.parse(file_content)
        self._report(on_progress, IngestStage.PARSING, 1.0)

        # ---- Step 2: 基于 PageIndex 构造 DocumentRecord ----
        # 从第一页的 metadata 推断文件类型
        source_type = (
            parsed_pages[0]["metadata"]["source_type"]
            if parsed_pages and "metadata" in parsed_pages[0]
            else "other"
        )
        file_type = SOURCE_TYPE_TO_FILE_TYPE.get(source_type, DocumentFileType.OTHER)

        # 推导文档标题
        if title is None:
            title = os.path.splitext(filename)[0]

        document_record = DocumentRecord(
            workspace_id=workspace_id,
            title=title,
            original_filename=filename,
            file_type=file_type,
            file_path=file_path,
            file_hash=file_hash,
            status=DocumentStatus.PARSED,
            page_count=len(parsed_pages),
        )

        # ---- Step 3: 基于 PageIndex 构造 DocumentUnit 列表 ----
        document_units: list[DocumentUnit] = []
        cumulative_offset = 0

        for i, page in enumerate(parsed_pages):
            content_len = len(page.get("content", ""))

            unit = DocumentUnit(
                document_id=document_record.id,
                sequence_index=i,
                text_content=page.get("content", ""),
                page_number=page.get("page_number"),
                start_char=cumulative_offset,
                end_char=cumulative_offset + content_len,
                token_count=None,  # 后续由 TokenService 计算
                metadata_json=page.get("metadata"),
                raw_content_json={
                    k: v for k, v in page.items()
                    if k != "content"  # content 已存入 text_content，避免重复
                },
                parser_name=page.get("parser_name"),
                parser_version=page.get("parser_version"),
            )
            document_units.append(unit)
            cumulative_offset += content_len

        # ---- Step 4: 切块 → 嵌入 → 落库（仅在注入 session_factory 时执行） ----
        # 顺序要点：**先算完再写**（见模块 docstring）。没有回调时也就不必分批。
        chunks_created = 0
        if self.session_factory is not None:
            chunks = self.chunk_service.split_units(document_units)
            with self._stage_span("ingest.embedding"):
                vectors = self._embed_chunks(chunks, on_progress)
            self._report(on_progress, IngestStage.PERSISTING, 0.0)
            with self._stage_span("ingest.persisting"):
                self._persist(document_record, document_units, chunks, vectors)
            self._report(on_progress, IngestStage.PERSISTING, 1.0)
            chunks_created = len(chunks)

        # ---- 构造返回结果 ----
        page_index_preview: list[dict[str, object]] = []
        for p in parsed_pages:
            preview_item: dict[str, object] = {
                "page_number": p["page_number"],
                "char_count": p["char_count"],
            }
            if "metadata" in p:
                preview_item["source_type"] = p["metadata"].get("source_type", "unknown")
            page_index_preview.append(preview_item)

        return {
            "filename": filename,
            "total_pages": len(parsed_pages),
            "status": "parsed_successfully",
            "page_index_preview": page_index_preview,
            "document_record": document_record,
            "document_units": document_units,
            "chunks_created": chunks_created,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
        }

    def _embed_chunks(
        self,
        chunks: list[Chunk],
        on_progress: ProgressCallback | None,
    ) -> list[list[float]]:
        """在**事务之外**嵌入全部片段，并上报嵌入阶段的进度。

        没有回调就没有"可见性"需求，也就不必分批 —— 直接走批量接口，
        它与分批路径得到同样的向量（分批不改语义）。
        """
        if not chunks:
            return []

        if on_progress is None:
            return self._get_embedding_service().embed_texts(
                [chunk.text_content for chunk in chunks]
            )

        return self._vector_builder().embed_chunks(
            chunks,
            on_progress=lambda processed, total: on_progress(
                IngestStage.EMBEDDING, processed / total
            ),
        )

    def _persist(
        self,
        record: DocumentRecord,
        units: list[DocumentUnit],
        chunks: list[Chunk],
        vectors: list[list[float]],
    ) -> None:
        """在同一事务里写入文档、单元、片段与向量。

        顺序由外键决定：文档 → 单元 → 片段 → 向量（向量再双写到 vec0 索引表）；
        中间两次 `flush` 是为了让下游 INSERT 满足外键约束（`PRAGMA foreign_keys = ON`）。
        向量在上游已经算好，这里只落库 —— 事务期间不加载模型，锁也就尽快释放。
        """
        with self.session_factory() as session:  # type: ignore[operator]
            DocumentRepository(session).save(record)

            unit_repository = DocumentUnitRepository(session)
            for unit in units:
                unit_repository.save(unit)
            session.flush()  # chunks 有 document_unit 外键，必须先落单元

            ChunkRepository(session).save_batch(chunks)
            session.flush()  # embedding_vectors 有 chunk 外键

            embedding_repository = EmbeddingRepository(
                session, embedding_dimension=self.embedding_dimension
            )
            self._vector_builder().write_vectors(embedding_repository, chunks, vectors)

            session.commit()

    def _stage_span(self, span_name: str) -> ContextManager[None]:
        """阶段 span 的上下文管理器；没接 recorder 时是空操作。

        属性在进入时就已确定（这里只有阶段名），所以用 `span()` 就够；
        需要"结束时才知道"的属性（页数、片段数）走 `_record`。
        """
        if self.trace_recorder is None:
            return nullcontext()
        return self.trace_recorder.span(span_name)

    def _record(
        self,
        span_name: str,
        duration_ms: float,
        *,
        status: TraceStatus = TraceStatus.OK,
        error: str | None = None,
        **attributes: object,
    ) -> None:
        """写一条 span；没接 recorder 时什么都不做。"""
        if self.trace_recorder is None:
            return
        self.trace_recorder.record_span(
            span_name=span_name,
            duration_ms=duration_ms,
            attributes=dict(attributes),
            status=status,
            error=error,
        )

    @staticmethod
    def _report(
        on_progress: ProgressCallback | None,
        stage: IngestStage,
        ratio: float,
    ) -> None:
        """上报阶段进度；没传回调就什么都不做。"""
        if on_progress is not None:
            on_progress(stage, ratio)

    def _vector_builder(self) -> VectorIndexBuilder:
        return VectorIndexBuilder(
            self._get_embedding_service(),
            embedding_model=self.embedding_model,
        )

    def _get_embedding_service(self) -> EmbeddingService:
        """懒加载生产嵌入服务（测试应注入假模型，绝不在这里触发模型下载）。"""
        if self.embedding_service is None:
            self.embedding_service = EmbeddingService(dimension=self.embedding_dimension)
        return self.embedding_service
