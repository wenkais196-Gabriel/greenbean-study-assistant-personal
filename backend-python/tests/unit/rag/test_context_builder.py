"""
ContextBuilder 单元测试：用假 repository 验证来源补全、跳过缺失与渲染标记。

对应规格：docs/specs/us-stage1-retrieval.md
"""
from app.entities import Chunk, DocumentUnit
from app.rag.context_builder import ContextBuilder
from app.rag.retriever import RetrievalHit


class FakeChunkRepository:
    def __init__(self, chunks: dict[str, Chunk]) -> None:
        self.chunks = chunks

    def get_by_id(self, chunk_id: str) -> Chunk | None:
        return self.chunks.get(chunk_id)


class FakeUnitRepository:
    def __init__(self, units: dict[str, DocumentUnit]) -> None:
        self.units = units

    def get_by_id(self, unit_id: str) -> DocumentUnit | None:
        return self.units.get(unit_id)


def make_unit(*, unit_id: str = "unit-1", document_id: str = "doc-1", page_number=3):
    return DocumentUnit(
        id=unit_id,
        document_id=document_id,
        sequence_index=0,
        text_content="Contenu du cours.",
        page_number=page_number,
    )


def make_chunk(
    *,
    chunk_id: str = "c1",
    unit_id: str = "unit-1",
    text: str = "Le polymorphisme est un concept fondamental.",
    heading_path: list[str] | None = None,
):
    return Chunk(
        id=chunk_id,
        document_unit_id=unit_id,
        sequence_index=0,
        text_content=text,
        metadata_json={"heading_path": heading_path or []},
    )


def make_builder(*, chunks, units):
    return ContextBuilder(FakeChunkRepository(chunks), FakeUnitRepository(units))


def test_build_enriches_hits_with_source_metadata():
    builder = make_builder(
        chunks={"c1": make_chunk(heading_path=["Chapitre 2"])},
        units={"unit-1": make_unit()},
    )

    items = builder.build([RetrievalHit(chunk_id="c1", distance=0.1)])

    assert len(items) == 1
    item = items[0]
    assert item.chunk_id == "c1"
    assert item.text == "Le polymorphisme est un concept fondamental."
    assert item.document_id == "doc-1"
    assert item.page_number == 3
    assert item.heading_path == ["Chapitre 2"]
    assert item.distance == 0.1


def test_build_skips_hits_whose_chunk_is_missing():
    builder = make_builder(chunks={}, units={"unit-1": make_unit()})

    items = builder.build([RetrievalHit(chunk_id="missing", distance=0.1)])

    assert items == []


def test_build_skips_hits_whose_unit_is_missing():
    builder = make_builder(
        chunks={"c1": make_chunk(unit_id="unit-missing")},
        units={},
    )

    items = builder.build([RetrievalHit(chunk_id="c1", distance=0.1)])

    assert items == []


def test_build_without_heading_path_returns_empty_list():
    builder = make_builder(chunks={"c1": make_chunk()}, units={"unit-1": make_unit()})

    items = builder.build([RetrievalHit(chunk_id="c1", distance=0.1)])

    assert items[0].heading_path == []


def test_render_marks_each_source_with_index_and_page():
    builder = make_builder(
        chunks={
            "c1": make_chunk(chunk_id="c1", text="Premier extrait."),
            "c2": make_chunk(chunk_id="c2", text="Deuxième extrait."),
        },
        units={"unit-1": make_unit()},
    )
    items = builder.build(
        [
            RetrievalHit(chunk_id="c1", distance=0.1),
            RetrievalHit(chunk_id="c2", distance=0.2),
        ]
    )

    rendered = builder.render(items)

    assert "[来源 1]" in rendered
    assert "[来源 2]" in rendered
    assert "Premier extrait." in rendered
    assert "Deuxième extrait." in rendered
    assert "第 3 页" in rendered


def test_render_omits_page_when_page_number_is_missing():
    builder = make_builder(
        chunks={"c1": make_chunk()},
        units={"unit-1": make_unit(page_number=None)},
    )
    items = builder.build([RetrievalHit(chunk_id="c1", distance=0.1)])

    rendered = builder.render(items)

    assert "None" not in rendered


def test_empty_hits_return_empty_items_and_empty_render():
    builder = make_builder(chunks={}, units={})

    items = builder.build([])
    rendered = builder.render(items)

    assert items == []
    assert rendered == ""
