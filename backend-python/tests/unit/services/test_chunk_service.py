"""
ChunkService 单元测试：覆盖切块的全部可观察行为。

对应规格：docs/specs/us-stage1-chunking.md
"""
import pytest

from app.entities import DocumentUnit
from app.services.chunk_service import ChunkService

DOCUMENT_ID = "doc-1"


def make_unit(
    text_content: str,
    *,
    headings: list[dict] | None = None,
    unit_id: str = "unit-1",
    page_number: int = 1,
    sequence_index: int = 0,
) -> DocumentUnit:
    """构造一个符合真实解析器输出的 DocumentUnit。"""
    return DocumentUnit(
        id=unit_id,
        document_id=DOCUMENT_ID,
        sequence_index=sequence_index,
        text_content=text_content,
        page_number=page_number,
        metadata_json={"source_type": "pdf", "headings": headings or []},
    )


# ---------- Happy path ----------


def test_short_unit_produces_single_chunk():
    """正文短于 chunk_size 的单元产生单个 Chunk，且溯源字段正确。"""
    text = "Le polymorphisme est un concept fondamental."
    unit = make_unit(text)

    chunks = ChunkService().split_unit(unit)

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.text_content == text
    assert chunk.sequence_index == 0
    assert chunk.start_char == 0
    assert chunk.end_char == len(text)
    assert chunk.document_unit_id == unit.id


def test_long_unit_is_split_into_multiple_chunks():
    """正文长于 chunk_size 两倍以上的单元被切成多个 Chunk。"""
    service = ChunkService(chunk_size=200, chunk_overlap=20)
    paragraphs = [f"Paragraphe {i} " + "x" * 80 for i in range(6)]
    unit = make_unit("\n\n".join(paragraphs))

    chunks = service.split_unit(unit)

    assert len(chunks) >= 2
    assert all(len(c.text_content) <= 200 for c in chunks)
    assert [c.sequence_index for c in chunks] == list(range(len(chunks)))


def test_splits_on_paragraph_boundary_when_possible():
    """优先在段落边界切断：第 1、2 段之和超过 chunk_size 时，第 1 个 Chunk 恰好是第 1 段。"""
    service = ChunkService(chunk_size=100, chunk_overlap=0)
    first = "A" * 60
    second = "B" * 60
    third = "C" * 60
    unit = make_unit(f"{first}\n\n{second}\n\n{third}")

    chunks = service.split_unit(unit)

    assert [c.text_content for c in chunks] == [first, second, third]


def test_long_single_paragraph_is_hard_split():
    """单个段落超过 chunk_size 时按窗口硬切，且不丢失字符。"""
    service = ChunkService(chunk_size=100, chunk_overlap=0)
    text = "x" * 350
    unit = make_unit(text)

    chunks = service.split_unit(unit)

    assert len(chunks) >= 3
    assert all(len(c.text_content) <= 100 for c in chunks)
    assert "".join(c.text_content for c in chunks) == text


def test_adjacent_chunks_overlap():
    """相邻 Chunk 之间保留配置的重叠字符。"""
    service = ChunkService(chunk_size=100, chunk_overlap=20)
    text = "x" * 250
    unit = make_unit(text)

    chunks = service.split_unit(unit)

    assert len(chunks) >= 2
    for previous, current in zip(chunks, chunks[1:]):
        assert current.text_content.startswith(previous.text_content[-20:])


# ---------- 溯源元数据 ----------


def test_chunk_records_heading_path():
    """每个 Chunk 记录自己所属的 heading 路径。"""
    headings = [
        {"level": 1, "text": "Chapitre 3"},
        {"level": 2, "text": "Le polymorphisme"},
    ]
    unit = make_unit("Contenu du chapitre.", headings=headings)

    chunks = ChunkService().split_unit(unit)

    assert chunks[0].metadata_json["heading_path"] == ["Chapitre 3", "Le polymorphisme"]


def test_unit_without_headings_still_chunks():
    """没有 headings 的单元（如 PDF）也能正常切块，路径为空列表。"""
    unit = make_unit("Contenu sans titre.", headings=[])

    chunks = ChunkService().split_unit(unit)

    assert len(chunks) == 1
    assert chunks[0].metadata_json["heading_path"] == []


def test_chunk_records_chunker_identity():
    """每个 Chunk 记录切块器名称与版本，便于日后追溯。"""
    unit = make_unit("Contenu.")

    chunk = ChunkService().split_unit(unit)[0]

    assert chunk.chunker_name
    assert chunk.chunker_version


# ---------- 边界 ----------


@pytest.mark.parametrize("blank_content", ["", "     ", "\n\n\n", "\t  \n"])
def test_blank_content_produces_no_chunks(blank_content):
    """空白正文不产生任何 Chunk。"""
    unit = make_unit(blank_content)

    assert ChunkService().split_unit(unit) == []


def test_text_length_equal_to_chunk_size_produces_single_chunk():
    """正文长度恰好等于 chunk_size 时只产生 1 个 Chunk，不产生空的第 2 个。"""
    service = ChunkService(chunk_size=100, chunk_overlap=10)
    text = "y" * 100
    unit = make_unit(text)

    chunks = service.split_unit(unit)

    assert len(chunks) == 1
    assert chunks[0].text_content == text


def test_empty_unit_list_returns_empty():
    """空单元列表返回空结果，不抛异常。"""
    assert ChunkService().split_units([]) == []


def test_consecutive_blank_lines_produce_no_empty_chunks():
    """段落之间的连续空行不产生空 Chunk。"""
    service = ChunkService(chunk_size=100, chunk_overlap=0)
    unit = make_unit("Premier paragraphe.\n\n\n\nDeuxième paragraphe.")

    chunks = service.split_unit(unit)

    assert chunks
    assert all(chunk.text_content.strip() for chunk in chunks)


# ---------- 失败路径 ----------


@pytest.mark.parametrize(
    ("chunk_size", "chunk_overlap"),
    [(500, 500), (500, 600), (0, 0), (-100, 10), (100, -1)],
)
def test_invalid_configuration_is_rejected(chunk_size, chunk_overlap):
    """非法配置直接抛 ValueError，不静默兜底。"""
    with pytest.raises(ValueError):
        ChunkService(chunk_size=chunk_size, chunk_overlap=chunk_overlap)


# ---------- 补充建议场景（已确认纳入） ----------


def test_chunking_is_idempotent_and_does_not_modify_unit():
    """切块是纯函数：重复切块结果一致，且不修改来源单元。"""
    service = ChunkService(chunk_size=100, chunk_overlap=10)
    unit = make_unit("x" * 250)
    original_text = unit.text_content
    original_token_count = unit.token_count

    first = service.split_unit(unit)
    second = service.split_unit(unit)

    assert [c.text_content for c in first] == [c.text_content for c in second]
    assert unit.text_content == original_text
    assert unit.token_count == original_token_count


def test_mixed_chinese_french_counts_by_characters():
    """中法混排文本按字符计数切分，不切断半个字符。"""
    service = ChunkService(chunk_size=10, chunk_overlap=0)
    text = "多态是面向对象编程的核心概念"
    unit = make_unit(text)

    chunks = service.split_unit(unit)

    assert len(chunks) == 2
    assert all(len(chunk.text_content) <= 10 for chunk in chunks)
    assert "".join(chunk.text_content for chunk in chunks) == text


def test_split_units_handles_multiple_units():
    """批量切块：每个 unit 各自产出 Chunk，序号在各自 unit 内独立从 0 开始。"""
    service = ChunkService()
    units = [
        make_unit("Premier contenu.", unit_id="unit-1"),
        make_unit("Deuxième contenu.", unit_id="unit-2"),
    ]

    chunks = service.split_units(units)

    assert [chunk.document_unit_id for chunk in chunks] == ["unit-1", "unit-2"]
    assert [chunk.sequence_index for chunk in chunks] == [0, 0]


def test_overlap_larger_than_segment_length_still_advances():
    """当段落比 chunk_overlap 还短时仍能推进，不产生重复或空片段。"""
    service = ChunkService(chunk_size=100, chunk_overlap=90)
    first = "A" * 60
    second = "B" * 60
    unit = make_unit(f"{first}\n\n{second}")

    chunks = service.split_unit(unit)

    assert [chunk.text_content for chunk in chunks] == [first, second]
