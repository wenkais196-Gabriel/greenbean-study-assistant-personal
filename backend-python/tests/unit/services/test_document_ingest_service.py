"""
文档摄取服务测试，覆盖 DocumentIngestService 全部逻辑。
"""
import pytest
from unittest.mock import MagicMock, patch
from app.services.document_ingest_service import DocumentIngestService, SOURCE_TYPE_TO_FILE_TYPE
from app.enums.document_file_type import DocumentFileType
from app.enums.document_status import DocumentStatus
from app.entities.document_record import DocumentRecord
from app.entities.document_unit import DocumentUnit

# 与下面"分批嵌入与进度回调"用例共用的假向量维度
DIMENSION = 8


# ---- 辅助：构造符合真实 parser 契约的 mock 返回值 ----

def _make_page(page_number=1, content="content", char_count=None, source_type="pdf",
               parser_name="PDFParser", parser_version="1.0.0", extra_meta=None):
    """构造一个符合真实 parser 输出格式的单页字典。"""
    meta = {"source_type": source_type}
    if extra_meta:
        meta.update(extra_meta)
    return {
        "page_number": page_number,
        "content": content,
        "char_count": char_count if char_count is not None else len(content),
        "parser_name": parser_name,
        "parser_version": parser_version,
        "metadata": meta,
    }


# ========== 对原有 7 条的增强版 ==========


@pytest.mark.us25
def test_ingest_pdf_document():
    """测试摄取 PDF 文档，验证返回字段和 document_record / document_units"""
    service = DocumentIngestService()

    with patch("app.parsers.parser_factory.ParserFactory.get_parser") as mock_get_parser:
        mock_parser = MagicMock()
        mock_parser.parse.return_value = [
            _make_page(page_number=1, content="PDF content", char_count=11, source_type="pdf",
                       parser_name="PDFParser", parser_version="1.0.0")
        ]
        mock_get_parser.return_value = mock_parser

        result = service.ingest_document("test.pdf", b"fake pdf content")

        # 原有断言
        assert result["filename"] == "test.pdf"
        assert result["total_pages"] == 1
        assert result["status"] == "parsed_successfully"
        assert result["page_index_preview"][0]["source_type"] == "pdf"
        assert result["page_index_preview"][0]["char_count"] == 11

        # 新增：验证 document_record
        record = result["document_record"]
        assert isinstance(record, DocumentRecord)
        assert record.original_filename == "test.pdf"
        assert record.file_type == DocumentFileType.PDF
        assert record.status == DocumentStatus.PARSED
        assert record.page_count == 1
        assert record.title == "test"  # 默认从文件名推导

        # 新增：验证 document_units
        units = result["document_units"]
        assert len(units) == 1
        unit = units[0]
        assert isinstance(unit, DocumentUnit)
        assert unit.document_id == record.id
        assert unit.sequence_index == 0
        assert unit.text_content == "PDF content"
        assert unit.page_number == 1
        assert unit.start_char == 0
        assert unit.end_char == 11
        assert unit.parser_name == "PDFParser"
        assert unit.parser_version == "1.0.0"
        assert unit.metadata_json == {"source_type": "pdf"}
        assert unit.raw_content_json == {
            "page_number": 1, "char_count": 11,
            "parser_name": "PDFParser", "parser_version": "1.0.0",
            "metadata": {"source_type": "pdf"},
        }


@pytest.mark.us25
def test_ingest_word_document():
    """测试摄取 Word 文档"""
    service = DocumentIngestService()

    with patch("app.parsers.parser_factory.ParserFactory.get_parser") as mock_get_parser:
        mock_parser = MagicMock()
        mock_parser.parse.return_value = [
            _make_page(page_number=1, content="Word content", char_count=12, source_type="word",
                       parser_name="WordParser", parser_version="1.0.0")
        ]
        mock_get_parser.return_value = mock_parser

        result = service.ingest_document("notes.docx", b"fake docx content")

        assert result["filename"] == "notes.docx"
        assert result["total_pages"] == 1
        assert result["page_index_preview"][0]["source_type"] == "word"

        # 验证 file_type 映射为 DOCX
        assert result["document_record"].file_type == DocumentFileType.DOCX
        assert len(result["document_units"]) == 1


@pytest.mark.us25
def test_ingest_image_document():
    """测试摄取图片文档"""
    service = DocumentIngestService()

    with patch("app.parsers.parser_factory.ParserFactory.get_parser") as mock_get_parser:
        mock_parser = MagicMock()
        mock_parser.parse.return_value = [
            _make_page(page_number=1, content="OCR text", char_count=8, source_type="image",
                       parser_name="ImageOCRParser", parser_version="1.0.0")
        ]
        mock_get_parser.return_value = mock_parser

        result = service.ingest_document("photo.png", b"fake image content")

        assert result["filename"] == "photo.png"
        assert result["total_pages"] == 1
        assert result["page_index_preview"][0]["source_type"] == "image"

        # 验证 file_type 映射为 IMAGE
        assert result["document_record"].file_type == DocumentFileType.IMAGE
        assert len(result["document_units"]) == 1


@pytest.mark.us25
def test_ingest_multiple_pages():
    """测试多页文档"""
    service = DocumentIngestService()

    with patch("app.parsers.parser_factory.ParserFactory.get_parser") as mock_get_parser:
        mock_parser = MagicMock()
        mock_parser.parse.return_value = [
            _make_page(page_number=1, content="Page 1", char_count=6,
                       parser_name="PDFParser", parser_version="1.0.0"),
            _make_page(page_number=2, content="Page 2", char_count=6,
                       parser_name="PDFParser", parser_version="1.0.0"),
        ]
        mock_get_parser.return_value = mock_parser

        result = service.ingest_document("multi.pdf", b"fake multi page content")

        assert result["total_pages"] == 2
        assert len(result["page_index_preview"]) == 2
        assert result["page_index_preview"][0]["page_number"] == 1
        assert result["page_index_preview"][1]["page_number"] == 2

        # 验证 document_units 数量及偏移
        units = result["document_units"]
        assert len(units) == 2
        assert units[0].start_char == 0
        assert units[0].end_char == 6
        assert units[1].start_char == 6
        assert units[1].end_char == 12
        assert result["document_record"].page_count == 2


@pytest.mark.us25
def test_ingest_unsupported_format():
    """测试不支持的文件格式"""
    service = DocumentIngestService()

    with patch("app.parsers.parser_factory.ParserFactory.get_parser") as mock_get_parser:
        mock_get_parser.side_effect = ValueError("暂不支持文件格式: file.ppt")

        with pytest.raises(ValueError, match="暂不支持文件格式"):
            service.ingest_document("file.ppt", b"content")


@pytest.mark.us25
def test_ingest_empty_content():
    """测试空内容文档"""
    service = DocumentIngestService()

    with patch("app.parsers.parser_factory.ParserFactory.get_parser") as mock_get_parser:
        mock_parser = MagicMock()
        mock_parser.parse.return_value = [
            _make_page(page_number=1, content="", char_count=0, source_type="pdf",
                       parser_name="PDFParser", parser_version="1.0.0")
        ]
        mock_get_parser.return_value = mock_parser

        result = service.ingest_document("empty.pdf", b"")

        assert result["total_pages"] == 1
        assert result["page_index_preview"][0]["char_count"] == 0

        # 空内容时 DocumentUnit 的 start_char == end_char
        unit = result["document_units"][0]
        assert unit.text_content == ""
        assert unit.start_char == 0
        assert unit.end_char == 0


@pytest.mark.us25
def test_ingest_no_metadata():
    """测试解析结果没有 metadata 的情况"""
    service = DocumentIngestService()

    with patch("app.parsers.parser_factory.ParserFactory.get_parser") as mock_get_parser:
        mock_parser = MagicMock()
        mock_parser.parse.return_value = [{
            "page_number": 1,
            "content": "No metadata",
            "char_count": 11,
            "parser_name": "SomeParser",
            "parser_version": "2.0.0",
            # 没有 metadata 字段
        }]
        mock_get_parser.return_value = mock_parser

        result = service.ingest_document("test.pdf", b"content")

        assert result["total_pages"] == 1
        # 没有 metadata 时，page_index_preview 中不包含 source_type 字段
        assert "source_type" not in result["page_index_preview"][0]

        # 没有 metadata 时，source_type 为 "other"，映射到 OTHER
        assert result["document_record"].file_type == DocumentFileType.OTHER

        # parser_name / parser_version 仍然通过 .get() 安全获取
        unit = result["document_units"][0]
        assert unit.parser_name == "SomeParser"
        assert unit.parser_version == "2.0.0"


# ========== 新增：SOURCE_TYPE_TO_FILE_TYPE 映射测试 ==========


@pytest.mark.us25
def test_source_type_to_file_type_pdf():
    """pdf → DocumentFileType.PDF"""
    assert SOURCE_TYPE_TO_FILE_TYPE["pdf"] == DocumentFileType.PDF


@pytest.mark.us25
def test_source_type_to_file_type_word():
    """word → DocumentFileType.DOCX"""
    assert SOURCE_TYPE_TO_FILE_TYPE["word"] == DocumentFileType.DOCX


@pytest.mark.us25
def test_source_type_to_file_type_ppt():
    """ppt → DocumentFileType.PPTX"""
    assert SOURCE_TYPE_TO_FILE_TYPE["ppt"] == DocumentFileType.PPTX


@pytest.mark.us25
def test_source_type_to_file_type_image():
    """image → DocumentFileType.IMAGE"""
    assert SOURCE_TYPE_TO_FILE_TYPE["image"] == DocumentFileType.IMAGE


@pytest.mark.us25
def test_source_type_to_file_type_text():
    """text → DocumentFileType.TEXT"""
    assert SOURCE_TYPE_TO_FILE_TYPE["text"] == DocumentFileType.TEXT


@pytest.mark.us25
def test_source_type_to_file_type_unknown_falls_back_to_other():
    """未识别的 source_type 应回退到 DocumentFileType.OTHER"""
    assert SOURCE_TYPE_TO_FILE_TYPE.get("unknown", DocumentFileType.OTHER) == DocumentFileType.OTHER


# ========== 新增：keyword args 测试 ==========


@pytest.mark.us25
def test_ingest_with_explicit_title():
    """传入 title keyword arg 应覆盖默认文件名推导"""
    service = DocumentIngestService()

    with patch("app.parsers.parser_factory.ParserFactory.get_parser") as mock_get_parser:
        mock_parser = MagicMock()
        mock_parser.parse.return_value = [
            _make_page(content="hello", source_type="text",
                       parser_name="TextParser", parser_version="1.0.0")
        ]
        mock_get_parser.return_value = mock_parser

        result = service.ingest_document("notes.txt", b"content", title="自定义标题")

        assert result["document_record"].title == "自定义标题"


@pytest.mark.us25
def test_ingest_with_workspace_id():
    """传入 workspace_id 应写入 document_record"""
    service = DocumentIngestService()

    with patch("app.parsers.parser_factory.ParserFactory.get_parser") as mock_get_parser:
        mock_parser = MagicMock()
        mock_parser.parse.return_value = [
            _make_page(content="x", source_type="text",
                       parser_name="TextParser", parser_version="1.0.0")
        ]
        mock_get_parser.return_value = mock_parser

        result = service.ingest_document("f.txt", b"content", workspace_id="ws-abc")

        assert result["document_record"].workspace_id == "ws-abc"


@pytest.mark.us25
def test_ingest_with_file_path():
    """传入 file_path 应写入 document_record"""
    service = DocumentIngestService()

    with patch("app.parsers.parser_factory.ParserFactory.get_parser") as mock_get_parser:
        mock_parser = MagicMock()
        mock_parser.parse.return_value = [
            _make_page(content="x", source_type="text",
                       parser_name="TextParser", parser_version="1.0.0")
        ]
        mock_get_parser.return_value = mock_parser

        result = service.ingest_document("f.txt", b"content", file_path="data/uploads/f.txt")

        assert result["document_record"].file_path == "data/uploads/f.txt"


@pytest.mark.us25
def test_ingest_with_file_hash():
    """传入 file_hash 应写入 document_record"""
    service = DocumentIngestService()

    with patch("app.parsers.parser_factory.ParserFactory.get_parser") as mock_get_parser:
        mock_parser = MagicMock()
        mock_parser.parse.return_value = [
            _make_page(content="x", source_type="text",
                       parser_name="TextParser", parser_version="1.0.0")
        ]
        mock_get_parser.return_value = mock_parser

        result = service.ingest_document("f.txt", b"content", file_hash="abc123")

        assert result["document_record"].file_hash == "abc123"


@pytest.mark.us25
def test_ingest_all_keyword_args():
    """同时传入所有 keyword args"""
    service = DocumentIngestService()

    with patch("app.parsers.parser_factory.ParserFactory.get_parser") as mock_get_parser:
        mock_parser = MagicMock()
        mock_parser.parse.return_value = [
            _make_page(content="hello", source_type="text",
                       parser_name="TextParser", parser_version="1.0.0")
        ]
        mock_get_parser.return_value = mock_parser

        result = service.ingest_document(
            "file.txt", b"content",
            workspace_id="ws-1",
            title="My Title",
            file_path="data/uploads/file.txt",
            file_hash="sha256:def456",
        )

        record = result["document_record"]
        assert record.workspace_id == "ws-1"
        assert record.title == "My Title"
        assert record.file_path == "data/uploads/file.txt"
        assert record.file_hash == "sha256:def456"


# ========== 新增：source_type 为 "other"（第一页无 metadata）回退到 OTHER ==========


@pytest.mark.us25
def test_ingest_first_page_no_metadata_falls_back_to_other():
    """第一页没有 metadata 时，source_type 为 'other'，file_type 应为 OTHER"""
    service = DocumentIngestService()

    with patch("app.parsers.parser_factory.ParserFactory.get_parser") as mock_get_parser:
        mock_parser = MagicMock()
        mock_parser.parse.return_value = [{
            "page_number": 1,
            "content": "no meta",
            "char_count": 7,
            "parser_name": "FakeParser",
            "parser_version": "0.0.1",
            # 无 metadata
        }]
        mock_get_parser.return_value = mock_parser

        result = service.ingest_document("test.pdf", b"content")

        assert result["document_record"].file_type == DocumentFileType.OTHER


# ========== 懒加载嵌入服务（不触发模型下载） ==========


def test_ingest_service_lazily_builds_and_reuses_embedding_service(monkeypatch):
    from app.services import document_ingest_service as ingest_module

    created: list[object] = []

    def fake_embedding_service(dimension: int):
        service = object()
        created.append(service)
        return service

    monkeypatch.setattr(ingest_module, "EmbeddingService", fake_embedding_service)

    service = DocumentIngestService(embedding_dimension=4)

    first = service._get_embedding_service()
    second = service._get_embedding_service()

    assert first is second
    assert created == [first]


# ========== 分批嵌入与进度回调（上传异步化的观测点） ==========


class _BatchEmbeddingModel:
    """按批返回确定向量；本文件只关心批的划分与回调，不关心向量值。"""

    def __init__(self) -> None:
        self.batch_sizes: list[int] = []

    def embed(self, texts, batch_size=None):
        batch = list(texts)
        self.batch_sizes.append(len(batch))
        for _ in enumerate(batch):
            yield [1.0] * DIMENSION


def test_ingest_reports_stage_progress_in_order(tmp_path):
    """阶段回调按 解析 → 嵌入 → 落库 推进，且每阶段的完成度走到 1.0。

    顺序不是随意的：SQLite 只允许一个写者，所以嵌入必须在落库之前完成
    （见 app/services/document_ingest_service.py 的模块 docstring）。
    用真 sqlite-vec + 假嵌入模型：验证的是"回调真的接在摄取流水线上"，不是回调函数本身。
    """
    from app.db.init_db import initialize_database, load_sqlite_vec_extension
    from app.db.orm import create_database_engine, create_session_factory
    from app.enums import IngestStage
    from app.services.embedding_service import EmbeddingService

    model = _BatchEmbeddingModel()
    initialization = initialize_database(
        data_dir=tmp_path / "data",
        database_name="progress.sqlite3",
        embedding_dimension=DIMENSION,
        sqlite_vec_loader=load_sqlite_vec_extension,
    )
    engine = create_database_engine(
        initialization.database_path,
        sqlite_vec_loader=load_sqlite_vec_extension,
    )
    try:
        service = DocumentIngestService(
            session_factory=create_session_factory(engine),
            embedding_service=EmbeddingService(
                model_name="fake-embedding-model",
                dimension=DIMENSION,
                model_factory=lambda name: model,
                query_prefix="",
                passage_prefix="",
            ),
            embedding_model="fake-embedding-model",
            embedding_dimension=DIMENSION,
        )

        with patch("app.parsers.parser_factory.ParserFactory.get_parser") as mock_get_parser:
            mock_parser = MagicMock()
            mock_parser.parse.return_value = [
                _make_page(page_number=1, content="premier paragraphe"),
                _make_page(page_number=2, content="deuxieme paragraphe"),
            ]
            mock_get_parser.return_value = mock_parser

            events: list[tuple[IngestStage, float]] = []
            service.ingest_document(
                "test.pdf",
                b"content",
                on_progress=lambda stage, ratio: events.append((stage, ratio)),
            )
    finally:
        engine.dispose()

    stages = [stage for stage, _ in events]
    assert stages == [
        IngestStage.PARSING,
        IngestStage.PARSING,
        IngestStage.EMBEDDING,
        IngestStage.PERSISTING,
        IngestStage.PERSISTING,
    ], "阶段顺序必须如实反映流水线：先算完（含嵌入）再落库"
    assert events[-1] == (IngestStage.PERSISTING, 1.0)
    assert model.batch_sizes == [2], "两个片段一批就够（默认批大小 16）"
    for stage in (IngestStage.PARSING, IngestStage.EMBEDDING, IngestStage.PERSISTING):
        ratios = [ratio for event_stage, ratio in events if event_stage is stage]
        assert ratios == sorted(ratios), f"{stage} 阶段内的完成度不能回退"


def test_ingest_without_progress_callback_embeds_in_one_batch(tmp_path):
    """不传回调时不分批：分批只是为了进度可见，没有观测者就没有必要。"""
    from app.db.init_db import initialize_database, load_sqlite_vec_extension
    from app.db.orm import create_database_engine, create_session_factory
    from app.services.embedding_service import EmbeddingService

    model = _BatchEmbeddingModel()
    initialization = initialize_database(
        data_dir=tmp_path / "data",
        database_name="no-progress.sqlite3",
        embedding_dimension=DIMENSION,
        sqlite_vec_loader=load_sqlite_vec_extension,
    )
    engine = create_database_engine(
        initialization.database_path,
        sqlite_vec_loader=load_sqlite_vec_extension,
    )
    try:
        service = DocumentIngestService(
            session_factory=create_session_factory(engine),
            embedding_service=EmbeddingService(
                model_name="fake-embedding-model",
                dimension=DIMENSION,
                model_factory=lambda name: model,
                query_prefix="",
                passage_prefix="",
            ),
            embedding_model="fake-embedding-model",
            embedding_dimension=DIMENSION,
        )

        with patch("app.parsers.parser_factory.ParserFactory.get_parser") as mock_get_parser:
            mock_parser = MagicMock()
            mock_parser.parse.return_value = [
                _make_page(page_number=1, content="premier paragraphe"),
                _make_page(page_number=2, content="deuxieme paragraphe"),
            ]
            mock_get_parser.return_value = mock_parser

            result = service.ingest_document("test.pdf", b"content")
    finally:
        engine.dispose()

    assert model.batch_sizes == [2], "没有回调时走一次性批量接口"
    assert result["chunks_created"] == 2


def test_parse_only_mode_reports_only_parsing():
    """不注入 session_factory 时是"只解析"模式：不该出现落库/嵌入阶段。"""
    from app.enums import IngestStage

    service = DocumentIngestService()

    with patch("app.parsers.parser_factory.ParserFactory.get_parser") as mock_get_parser:
        mock_parser = MagicMock()
        mock_parser.parse.return_value = [_make_page(page_number=1, content="texte")]
        mock_get_parser.return_value = mock_parser

        events: list[tuple[IngestStage, float]] = []
        service.ingest_document(
            "test.pdf",
            b"content",
            on_progress=lambda stage, ratio: events.append((stage, ratio)),
        )

    assert [stage for stage, _ in events] == [IngestStage.PARSING, IngestStage.PARSING]


def test_ingest_of_a_document_with_no_pages_persists_nothing(tmp_path):
    """解析出 0 页的文档：没有片段可嵌入，摄取也不该因为空列表报错。"""
    from app.db.init_db import initialize_database, load_sqlite_vec_extension
    from app.db.orm import create_database_engine, create_session_factory
    from app.services.embedding_service import EmbeddingService

    model = _BatchEmbeddingModel()
    initialization = initialize_database(
        data_dir=tmp_path / "data",
        database_name="no-pages.sqlite3",
        embedding_dimension=DIMENSION,
        sqlite_vec_loader=load_sqlite_vec_extension,
    )
    engine = create_database_engine(
        initialization.database_path,
        sqlite_vec_loader=load_sqlite_vec_extension,
    )
    try:
        service = DocumentIngestService(
            session_factory=create_session_factory(engine),
            embedding_service=EmbeddingService(
                model_name="fake-embedding-model",
                dimension=DIMENSION,
                model_factory=lambda name: model,
                query_prefix="",
                passage_prefix="",
            ),
            embedding_model="fake-embedding-model",
            embedding_dimension=DIMENSION,
        )

        with patch("app.parsers.parser_factory.ParserFactory.get_parser") as mock_get_parser:
            mock_parser = MagicMock()
            mock_parser.parse.return_value = []
            mock_get_parser.return_value = mock_parser

            result = service.ingest_document(
                "empty.pdf", b"content", on_progress=lambda stage, ratio: None
            )
    finally:
        engine.dispose()

    assert result["total_pages"] == 0
    assert result["chunks_created"] == 0
    assert model.batch_sizes == [], "没有片段就不该调用模型"
