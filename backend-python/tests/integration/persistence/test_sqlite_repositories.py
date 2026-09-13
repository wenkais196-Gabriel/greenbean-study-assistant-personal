import sqlite3

import sqlite_vec

import pytest

from app.db.init_db import initialize_database
from app.db.orm import create_database_engine, create_session_factory
from app.entities import (
    AnalysisResult,
    ChatMessage,
    ChatSession,
    Chunk,
    DocumentRecord,
    DocumentUnit,
    ProviderConfig,
    Section,
)
from app.enums import AnalysisType, ApiMode, DocumentFileType, MessageRole
from app.repositories.analysis_result_repository import AnalysisResultRepository
from app.repositories.chat_message_repository import ChatMessageRepository
from app.repositories.chat_session_repository import ChatSessionRepository
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.document_unit_repository import DocumentUnitRepository
from app.repositories.embedding_repository import (
    EmbeddingDimensionError,
    EmbeddingRepository,
    MissingChunkError,
)
from app.repositories.provider_config_repository import ProviderConfigRepository
from app.repositories.section_repository import SectionRepository


def load_test_sqlite_vec(connection: sqlite3.Connection) -> None:
    """真加载 sqlite-vec（vec0 模块是建索引表的前提），但把 vec_version 覆盖为固定测试值。"""
    connection.enable_load_extension(True)
    try:
        sqlite_vec.load(connection)
    finally:
        connection.enable_load_extension(False)
    connection.create_function("vec_version", 0, lambda: "test-sqlite-vec")


@pytest.fixture
def session_factory(tmp_path):
    result = initialize_database(
        data_dir=tmp_path / "data",
        sqlite_vec_loader=load_test_sqlite_vec,
        embedding_dimension=8,
    )
    engine = create_database_engine(
        result.database_path,
        sqlite_vec_loader=load_test_sqlite_vec,
    )
    yield create_session_factory(engine)
    engine.dispose()


def make_core_learning_data():
    document = DocumentRecord(
        workspace_id="workspace_1",
        title="Course Deck",
        original_filename="course.pptx",
        file_type=DocumentFileType.PPTX,
        file_path="data/uploads/course.pptx",
        page_count=12,
    )
    unit = DocumentUnit(
        document_id=document.id,
        sequence_index=0,
        text_content="Slide 1 introduces the course objectives.",
        page_number=1,
        metadata_json={"unit_kind": "slide"},
    )
    section = Section(
        document_id=document.id,
        title="Course objectives",
        level=1,
        order_index=0,
        start_page=1,
        end_page=2,
        metadata_json={"source_unit_ids": [unit.id]},
    )
    chunk = Chunk(
        document_unit_id=unit.id,
        sequence_index=0,
        text_content="Course objectives and grading policy.",
        start_char=0,
        end_char=37,
        token_count=6,
    )
    analysis_result = AnalysisResult(
        document_id=document.id,
        section_id=section.id,
        analysis_type=AnalysisType.SECTION,
        language="zh",
        content_markdown="课程目标总结",
        summary="课程目标摘要",
        model_name="test-model",
    )
    chat_session = ChatSession(
        workspace_id="workspace_1",
        document_id=document.id,
        title="Course Q&A",
    )
    chat_message = ChatMessage(
        session_id=chat_session.id,
        role=MessageRole.USER,
        content="课程考核方式是什么？",
        source_context_json={"chunk_ids": [chunk.id]},
    )
    return document, unit, section, chunk, analysis_result, chat_session, chat_message


def test_repositories_persist_core_learning_data_after_reconnect(session_factory):
    document, unit, section, chunk, analysis_result, chat_session, chat_message = make_core_learning_data()

    with session_factory() as session:
        DocumentRepository(session).save(document)
        DocumentUnitRepository(session).save(unit)
        SectionRepository(session).save(section)
        ChunkRepository(session).save(chunk)
        AnalysisResultRepository(session).save(analysis_result)
        ChatSessionRepository(session).save(chat_session)
        ChatMessageRepository(session).save(chat_message)
        session.commit()

    with session_factory() as session:
        assert DocumentRepository(session).get_by_id(document.id).title == "Course Deck"
        assert DocumentUnitRepository(session).get_by_id(unit.id).text_content == unit.text_content
        assert SectionRepository(session).get_by_id(section.id).title == "Course objectives"
        assert ChunkRepository(session).get_by_id(chunk.id).document_unit_id == unit.id
        persisted_analysis = AnalysisResultRepository(session).get_by_id(analysis_result.id)
        assert persisted_analysis.section_id == section.id
        assert persisted_analysis.summary == "课程目标摘要"
        assert ChatSessionRepository(session).get_by_id(chat_session.id).document_id == document.id
        assert ChatMessageRepository(session).get_by_id(chat_message.id).session_id == chat_session.id


def test_embedding_repository_saves_chunk_embedding_and_traces_to_document_unit(session_factory):
    document, unit, _, chunk, *_ = make_core_learning_data()

    with session_factory() as session:
        DocumentRepository(session).save(document)
        DocumentUnitRepository(session).save(unit)
        ChunkRepository(session).save(chunk)

        embedding = EmbeddingRepository(session, embedding_dimension=8).save_for_chunk(
            chunk_id=chunk.id,
            embedding_model="test-embedding-model",
            vector=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8],
        )
        session.commit()

    with session_factory() as session:
        persisted = EmbeddingRepository(session, embedding_dimension=8).get_by_chunk_id(chunk.id)
        persisted_chunk = ChunkRepository(session).get_by_id(persisted.chunk_id)

    assert embedding.chunk_id == chunk.id
    assert persisted.chunk_id == chunk.id
    assert persisted.vector_dimension == 8
    assert persisted.vector == [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
    assert persisted_chunk.document_unit_id == unit.id


def test_embedding_repository_rejects_dimension_mismatch(session_factory):
    document, unit, _, chunk, *_ = make_core_learning_data()

    with session_factory() as session:
        DocumentRepository(session).save(document)
        DocumentUnitRepository(session).save(unit)
        ChunkRepository(session).save(chunk)

        with pytest.raises(EmbeddingDimensionError, match="dimension"):
            EmbeddingRepository(session, embedding_dimension=8).save_for_chunk(
                chunk_id=chunk.id,
                embedding_model="test-embedding-model",
                vector=[0.1, 0.2],
            )


def test_embedding_repository_rejects_missing_chunk(session_factory):
    with session_factory() as session:
        with pytest.raises(MissingChunkError, match="missing-chunk"):
            EmbeddingRepository(session, embedding_dimension=8).save_for_chunk(
                chunk_id="missing-chunk",
                embedding_model="test-embedding-model",
                vector=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8],
            )


def make_provider_config(name: str = "test-cfg", is_active: bool = False) -> ProviderConfig:
    return ProviderConfig(
        name=name, api_mode=ApiMode.OPENAI_COMPAT, api_key="sk-test",
        api_host="https://api.test.com", model_id="test-model",
        display_name=name, is_active=is_active,
    )


def test_provider_config_repository_save_and_get_by_id(session_factory):
    config = make_provider_config()
    with session_factory() as session:
        ProviderConfigRepository(session).save(config)
        session.commit()
    with session_factory() as session:
        loaded = ProviderConfigRepository(session).get_by_id(config.id)
        assert loaded.name == "test-cfg"
        assert loaded.api_mode == ApiMode.OPENAI_COMPAT


def test_provider_config_repository_get_by_name(session_factory):
    config = make_provider_config(name="unique-name")
    with session_factory() as session:
        ProviderConfigRepository(session).save(config)
        session.commit()
    with session_factory() as session:
        loaded = ProviderConfigRepository(session).get_by_name("unique-name")
        assert loaded.id == config.id


def test_provider_config_repository_get_by_name_returns_none(session_factory):
    with session_factory() as session:
        assert ProviderConfigRepository(session).get_by_name("nonexistent") is None


def test_provider_config_repository_get_active(session_factory):
    config = make_provider_config(name="active-one", is_active=True)
    with session_factory() as session:
        ProviderConfigRepository(session).save(config)
        session.commit()
    with session_factory() as session:
        assert ProviderConfigRepository(session).get_active().name == "active-one"


def test_provider_config_repository_get_active_returns_none_when_none_active(session_factory):
    config = make_provider_config(is_active=False)
    with session_factory() as session:
        ProviderConfigRepository(session).save(config)
        session.commit()
    with session_factory() as session:
        assert ProviderConfigRepository(session).get_active() is None


def test_provider_config_repository_deactivate_all(session_factory):
    with session_factory() as session:
        repo = ProviderConfigRepository(session)
        repo.save(make_provider_config(name="c1", is_active=True))
        repo.save(make_provider_config(name="c2", is_active=True))
        repo.deactivate_all()
        session.commit()
    with session_factory() as session:
        assert ProviderConfigRepository(session).get_active() is None


def test_provider_config_repository_list_all(session_factory):
    with session_factory() as session:
        repo = ProviderConfigRepository(session)
        repo.save(make_provider_config(name="a"))
        repo.save(make_provider_config(name="b"))
        session.commit()
    with session_factory() as session:
        names = [c.name for c in ProviderConfigRepository(session).list_all()]
        assert "a" in names and "b" in names


def test_provider_config_repository_delete(session_factory):
    config = make_provider_config()
    with session_factory() as session:
        ProviderConfigRepository(session).save(config)
        session.commit()
    with session_factory() as session:
        assert ProviderConfigRepository(session).delete(config.id) is True
        session.commit()
    with session_factory() as session:
        assert ProviderConfigRepository(session).get_by_id(config.id) is None


def test_provider_config_repository_delete_nonexistent(session_factory):
    with session_factory() as session:
        assert ProviderConfigRepository(session).delete("nonexistent-id") is False


def test_provider_config_repository_update(session_factory):
    config = make_provider_config(name="original")
    with session_factory() as session:
        repo = ProviderConfigRepository(session)
        repo.save(config)
        session.commit()
        config.name = "updated"
        repo.save(config)
        session.commit()
    with session_factory() as session:
        assert ProviderConfigRepository(session).get_by_id(config.id).name == "updated"


def test_analysis_result_repository_get_by_workspace_id(session_factory):
    """analysis_results 没有 workspace 列 —— 查询要经 document_records 关联过滤。"""
    in_scope_document, *_ = make_core_learning_data()
    other_document = DocumentRecord(
        workspace_id="workspace_2",
        title="Autre cours",
        original_filename="autre.pdf",
        file_type=DocumentFileType.PDF,
        file_path="data/uploads/autre.pdf",
    )

    with session_factory() as session:
        DocumentRepository(session).save(in_scope_document)
        DocumentRepository(session).save(other_document)
        AnalysisResultRepository(session).save(
            AnalysisResult(
                document_id=in_scope_document.id,
                analysis_type=AnalysisType.FULL_DOCUMENT,
                language="zh",
                content_markdown="工作区一的全文分析",
                summary="工作区一的摘要",
            )
        )
        AnalysisResultRepository(session).save(
            AnalysisResult(
                document_id=other_document.id,
                analysis_type=AnalysisType.FULL_DOCUMENT,
                language="zh",
                content_markdown="工作区二的全文分析",
                summary="工作区二的摘要",
            )
        )
        session.commit()

    with session_factory() as session:
        results = AnalysisResultRepository(session).get_by_workspace_id("workspace_1")

    assert [result.summary for result in results] == ["工作区一的摘要"]


def test_analysis_result_repository_get_by_workspace_id_returns_empty_list_when_unmatched(
    session_factory,
):
    with session_factory() as session:
        assert AnalysisResultRepository(session).get_by_workspace_id("inconnu") == []

