"""使用真实 PDF 验证文档解析与摄取流水线。"""

from pathlib import Path

import pytest

from app.enums.document_file_type import DocumentFileType
from app.enums.document_status import DocumentStatus
from app.parsers.parser_factory import ParserFactory
from app.parsers.pdf_parser import PDFParser
from app.services.document_ingest_service import DocumentIngestService


pytestmark = [pytest.mark.integration, pytest.mark.us25]

EXPECTED_PAGE_COUNT = 2
# 这份 PDF 由 scripts/make_synthetic_corpus.py 自产（不再用上游带进来的真实课程文档），
# 下面是它输出的真实字符数：改语料就要同步改这里，`--check` 会拦住产物与脚本不一致的情况。
EXPECTED_CHARACTER_COUNTS = [1837, 902]


def test_pdf_parser_extracts_text_from_real_pdf(
    text_two_pages_pdf_path: Path,
    text_two_pages_pdf_bytes: bytes,
):
    pages = PDFParser().parse(text_two_pages_pdf_bytes)

    assert text_two_pages_pdf_path.name == "text_two_pages.pdf"
    assert len(pages) == EXPECTED_PAGE_COUNT
    assert [page["page_number"] for page in pages] == [1, 2]
    assert [page["char_count"] for page in pages] == EXPECTED_CHARACTER_COUNTS
    assert all(page["char_count"] == len(page["content"]) for page in pages)
    assert all(page["content"] for page in pages)
    assert all(page["parser_name"] == "PDFParser" for page in pages)
    assert all(page["parser_version"] == "1.1.0" for page in pages)
    assert all(page["metadata"]["source_type"] == "pdf" for page in pages)


def test_parser_factory_routes_real_pdf_to_pdf_parser(
    text_two_pages_pdf_bytes: bytes,
):
    parser = ParserFactory.get_parser("text_two_pages.pdf")

    assert isinstance(parser, PDFParser)
    assert [
        page["char_count"] for page in parser.parse(text_two_pages_pdf_bytes)
    ] == EXPECTED_CHARACTER_COUNTS


def test_document_ingest_service_builds_entities_from_real_pdf(
    text_two_pages_pdf_bytes: bytes,
):
    result = DocumentIngestService().ingest_document(
        "text_two_pages.pdf",
        text_two_pages_pdf_bytes,
    )

    record = result["document_record"]
    units = result["document_units"]

    assert result["filename"] == "text_two_pages.pdf"
    assert result["total_pages"] == EXPECTED_PAGE_COUNT
    assert result["status"] == "parsed_successfully"
    assert record.original_filename == "text_two_pages.pdf"
    assert record.file_type == DocumentFileType.PDF
    assert record.status == DocumentStatus.PARSED
    assert record.page_count == EXPECTED_PAGE_COUNT
    assert len(units) == EXPECTED_PAGE_COUNT
    assert [unit.page_number for unit in units] == [1, 2]
    assert [len(unit.text_content) for unit in units] == EXPECTED_CHARACTER_COUNTS
    assert all(unit.parser_name == "PDFParser" for unit in units)
    assert all(
        preview["source_type"] == "pdf"
        for preview in result["page_index_preview"]
    )
