"""
上传摄取的 trace：总 span + 三个阶段 span，且写 trace 不破坏摄取本身。

用真 sqlite-vec + 假嵌入模型 + 假解析器（CI 不下载模型）。
对应规格：docs/specs/us-stage1-trace.md（AC5 / AC6 / AC7）
"""
from unittest.mock import MagicMock, patch

import pytest

from app.db.init_db import initialize_database, load_sqlite_vec_extension
from app.db.orm import create_database_engine, create_session_factory
from app.enums import TraceStatus
from app.services.document_ingest_service import DocumentIngestService
from app.services.embedding_service import EmbeddingService
from app.services.trace_recorder import TraceRecorder
from app.utils.trace_context import bind_trace, reset_trace

pytestmark = [pytest.mark.integration]

DIMENSION = 8
MODEL_NAME = "fake-embedding-model"
FIXED_TRACE_ID = "ingest-trace"

EXPECTED_SPANS = ["ingest.parsing", "ingest.embedding", "ingest.persisting", "ingest.document"]


class FakeEmbeddingModel:
    def embed(self, texts, batch_size=None):
        for _ in enumerate(list(texts)):
            yield [1.0] * DIMENSION


def make_page(page_number: int, content: str) -> dict:
    return {
        "page_number": page_number,
        "content": content,
        "char_count": len(content),
        "parser_name": "FakeParser",
        "parser_version": "1.0.0",
        "metadata": {"source_type": "pdf"},
    }


@pytest.fixture
def ingest_env(tmp_path):
    initialization = initialize_database(
        data_dir=tmp_path / "data",
        database_name="ingest-trace.sqlite3",
        embedding_dimension=DIMENSION,
        sqlite_vec_loader=load_sqlite_vec_extension,
    )
    engine = create_database_engine(
        initialization.database_path,
        sqlite_vec_loader=load_sqlite_vec_extension,
    )
    session_factory = create_session_factory(engine)
    recorder = TraceRecorder(session_factory=session_factory)
    service = DocumentIngestService(
        session_factory=session_factory,
        embedding_service=EmbeddingService(
            model_name=MODEL_NAME,
            dimension=DIMENSION,
            model_factory=lambda name: FakeEmbeddingModel(),
            query_prefix="",
            passage_prefix="",
        ),
        embedding_model=MODEL_NAME,
        embedding_dimension=DIMENSION,
        trace_recorder=recorder,
    )
    try:
        yield service, recorder
    finally:
        engine.dispose()


def ingest(service, pages, *, content=b"%PDF-1.4"):
    with patch("app.parsers.parser_factory.ParserFactory.get_parser") as mock_get_parser:
        mock_parser = MagicMock()
        mock_parser.parse.return_value = pages
        mock_get_parser.return_value = mock_parser

        token = bind_trace(FIXED_TRACE_ID)
        try:
            return service.ingest_document("cours.pdf", content, workspace_id="ws-1")
        finally:
            reset_trace(token)


def test_ingestion_writes_a_document_span_and_three_stage_spans(ingest_env):
    service, recorder = ingest_env

    result = ingest(service, [make_page(1, "premier"), make_page(2, "deuxieme")])

    spans = recorder.get_trace(FIXED_TRACE_ID)
    assert [span.span_name for span in spans] == EXPECTED_SPANS
    assert all(span.status is TraceStatus.OK for span in spans)

    document = spans[-1]
    assert document.attributes["greenbean.ingest.pages"] == 2
    assert document.attributes["greenbean.ingest.chunks_created"] == result["chunks_created"]
    assert document.attributes["greenbean.ingest.elapsed_seconds"] >= 0


def test_stage_spans_carry_durations(ingest_env):
    service, recorder = ingest_env

    ingest(service, [make_page(1, "premier")])

    by_name = {span.span_name: span for span in recorder.get_trace(FIXED_TRACE_ID)}
    for name in ("ingest.parsing", "ingest.embedding", "ingest.persisting"):
        assert by_name[name].duration_ms >= 0


def test_failed_ingestion_is_traced_and_the_error_still_propagates(ingest_env):
    """trace 是观测层：记录失败，但不能把失败吞掉。"""
    service, recorder = ingest_env

    with pytest.raises(ValueError, match="解析器无法解析"):
        with patch("app.parsers.parser_factory.ParserFactory.get_parser") as mock_get_parser:
            mock_get_parser.side_effect = ValueError("解析器无法解析该文件")

            token = bind_trace(FIXED_TRACE_ID)
            try:
                service.ingest_document("cours.pdf", b"broken")
            finally:
                reset_trace(token)

    spans = recorder.get_trace(FIXED_TRACE_ID)
    assert [span.span_name for span in spans] == ["ingest.parsing", "ingest.document"], (
        "阶段 span 与总 span 都要留下失败记录"
    )
    assert all(span.status is TraceStatus.ERROR for span in spans)
    assert spans[0].error is not None and "解析器无法解析" in spans[0].error


def test_ingestion_without_a_recorder_is_unchanged(ingest_env):
    """不注入 recorder 时行为与从前完全一致 —— trace 关闭态走的就是这条路。"""
    service, _ = ingest_env
    bare = DocumentIngestService(
        session_factory=service.session_factory,
        embedding_service=service.embedding_service,
        embedding_model=MODEL_NAME,
        embedding_dimension=DIMENSION,
    )

    assert bare.trace_recorder is None, "默认不接 trace：避免测试误写生产库"

    result = ingest(bare, [make_page(1, "premier")])

    assert result["chunks_created"] >= 1
