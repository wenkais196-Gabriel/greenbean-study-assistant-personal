"""
文档摄取服务：解析 → 实体构建 → 落库 → 切块 → 向量化。

两种运行模式（沿用上游"渐进式交付"的分阶段思路）：

- **完整摄取**：注入了 `session_factory` 时，在**同一事务**里写入
  `document_records` / `document_units` / `chunks` / `embedding_vectors` / `embedding_index`，
  完成后数据即可被检索链路（Retriever / ContextBuilder）直接使用；
- **只解析**：未注入时只解析并构造实体（预览用，不碰数据库）。

⚠️ 嵌入在 CPU 上不是即时操作（e5-large 实测约 200 ms/片段，290 页资料约 112 s）：
调用方应把它放进线程池执行，别阻塞事件循环（见 `document_controller`）。
"""
import os
import time

from app.config.settings import EMBEDDING_DIMENSION, EMBEDDING_MODEL
from app.db.orm import SessionFactory
from app.entities import DocumentRecord, DocumentUnit
from app.enums.document_file_type import DocumentFileType
from app.enums.document_status import DocumentStatus
from app.parsers.parser_factory import ParserFactory
from app.rag.vector_index_builder import VectorIndexBuilder
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.document_unit_repository import DocumentUnitRepository
from app.repositories.embedding_repository import EmbeddingRepository
from app.services.chunk_service import ChunkService
from app.services.embedding_service import EmbeddingService

# source_type → DocumentFileType 映射常量
SOURCE_TYPE_TO_FILE_TYPE: dict[str, DocumentFileType] = {
    "pdf": DocumentFileType.PDF,
    "word": DocumentFileType.DOCX,
    "ppt": DocumentFileType.PPTX,
    "image": DocumentFileType.IMAGE,
    "text": DocumentFileType.TEXT,
}


class DocumentIngestService:
    """安全文档摄取流水线：解析 → 实体构建 → （可选）落库 → 切块 → 向量化。"""

    def __init__(
        self,
        *,
        session_factory: SessionFactory | None = None,
        chunk_service: ChunkService | None = None,
        embedding_service: EmbeddingService | None = None,
        embedding_model: str = EMBEDDING_MODEL,
        embedding_dimension: int = EMBEDDING_DIMENSION,
    ) -> None:
        """
        :param session_factory: 会话工厂；**注入即开启完整摄取**（落库 + 切块 + 向量化），
            不注入则只做解析与实体构建
        :param chunk_service: 切块服务，默认用生产配置的 `ChunkService()`
        :param embedding_service: 嵌入服务，默认懒加载生产配置（**测试请注入假模型**）
        :param embedding_model: 写入 `embedding_vectors.embedding_model` 供追溯
        :param embedding_dimension: 向量维度，必须与建库时的 vec0 维度一致
        """
        self.session_factory = session_factory
        self.chunk_service = chunk_service or ChunkService()
        self.embedding_service = embedding_service
        self.embedding_model = embedding_model
        self.embedding_dimension = embedding_dimension

    def ingest_document(
        self,
        filename: str,
        file_content: bytes,
        *,
        workspace_id: str = "",
        title: str | None = None,
        file_path: str = "",
        file_hash: str | None = None,
    ) -> dict:
        """
        贯穿整个文件流的摄取流水线。

        :param filename: 文件名（含扩展名）
        :param file_content: 文件二进制数据
        :param workspace_id: 所属工作区 ID
        :param title: 文档标题，不传则从文件名推导
        :param file_path: 原始文件在本地 uploads 目录下的路径
        :param file_hash: 原始文件哈希值
        :return: 解析结果字典，含 document_record / document_units / chunks_created / elapsed_seconds
        """
        started = time.perf_counter()

        # ---- Step 1: 通过工厂匹配解析器并提取 PageIndex 原始单页文本 ----
        parser = ParserFactory.get_parser(filename)
        parsed_pages = parser.parse(file_content)

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

        # ---- Step 4: 落库 + 切块 + 向量化（仅在注入 session_factory 时执行） ----
        chunks_created = 0
        if self.session_factory is not None:
            chunks_created = self._persist(document_record, document_units)

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

    def _persist(self, record: DocumentRecord, units: list[DocumentUnit]) -> int:
        """在同一事务里写入文档、单元、片段与向量，返回写入的片段数。

        顺序由外键决定：文档 → 单元 → 片段 → 向量（向量再双写到 vec0 索引表）；
        中间两次 `flush` 是为了让下游 INSERT 满足外键约束（`PRAGMA foreign_keys = ON`）。
        """
        with self.session_factory() as session:  # type: ignore[operator]
            DocumentRepository(session).save(record)

            unit_repository = DocumentUnitRepository(session)
            for unit in units:
                unit_repository.save(unit)
            session.flush()  # chunks 有 document_unit 外键，必须先落单元

            chunks = self.chunk_service.split_units(units)
            ChunkRepository(session).save_batch(chunks)
            session.flush()  # embedding_vectors 有 chunk 外键

            embedding_repository = EmbeddingRepository(
                session, embedding_dimension=self.embedding_dimension
            )
            VectorIndexBuilder(
                self._get_embedding_service(),
                embedding_model=self.embedding_model,
            ).build_for_chunks(embedding_repository, chunks)

            session.commit()

        return len(chunks)

    def _get_embedding_service(self) -> EmbeddingService:
        """懒加载生产嵌入服务（测试应注入假模型，绝不在这里触发模型下载）。"""
        if self.embedding_service is None:
            self.embedding_service = EmbeddingService(dimension=self.embedding_dimension)
        return self.embedding_service
