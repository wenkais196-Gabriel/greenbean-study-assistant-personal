"""
Chunk 服务：把解析后的 DocumentUnit 切成可溯源的语义片段。

设计取舍见 docs/specs/us-stage1-chunking.md：
- 段落优先：切点尽量落在一个空行之后；只有单个段落本身超过 chunk_size 时才按窗口硬切；
- 相邻片段保留 chunk_overlap 个字符的重叠，避免跨边界的信息丢失；
- 每个片段记录所属 heading 路径，供后续引用回溯使用；
- 切块是纯函数：不修改来源 DocumentUnit，重复切块结果一致。
"""
import re

from app.config.settings import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE
from app.entities import Chunk, DocumentUnit

CHUNKER_NAME = "paragraph_window_chunker"
CHUNKER_VERSION = "1.0.0"

# 段落分隔：一个空行（中间允许夹杂空白字符）
_PARAGRAPH_SEPARATOR = re.compile(r"\n\s*\n")


class ChunkService:
    """在单个 DocumentUnit 内部切块，并保留页码与标题路径的溯源信息。"""

    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError(f"chunk_size 必须为正整数，当前为 {chunk_size}")
        if chunk_overlap < 0 or chunk_overlap >= chunk_size:
            raise ValueError(
                "chunk_overlap 需满足 0 <= overlap < chunk_size，"
                f"当前 chunk_size={chunk_size}, chunk_overlap={chunk_overlap}"
            )
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split_units(self, units: list[DocumentUnit]) -> list[Chunk]:
        """批量切块；每个 unit 内的 sequence_index 各自从 0 开始。"""
        chunks: list[Chunk] = []
        for unit in units:
            chunks.extend(self.split_unit(unit))
        return chunks

    def split_unit(self, unit: DocumentUnit) -> list[Chunk]:
        """把一个 DocumentUnit 切成若干 Chunk；正文为空白时返回空列表。"""
        text = unit.text_content
        if not text.strip():
            return []

        heading_path = self._extract_heading_path(unit)
        chunks: list[Chunk] = []
        for start, end in self._split_spans(text):
            content = text[start:end]
            chunks.append(
                Chunk(
                    document_unit_id=unit.id,
                    sequence_index=len(chunks),
                    text_content=content,
                    start_char=start,
                    end_char=end,
                    metadata_json={"heading_path": heading_path},
                    chunker_name=CHUNKER_NAME,
                    chunker_version=CHUNKER_VERSION,
                )
            )
        return chunks

    def _split_spans(self, text: str) -> list[tuple[int, int]]:
        """计算每个 Chunk 在 unit 正文中的 (start, end) 区间。"""
        text_length = len(text)
        spans: list[tuple[int, int]] = []
        position = 0

        while position < text_length:
            limit = min(position + self.chunk_size, text_length)
            end = self._align_to_paragraph(text, position, limit)
            spans.append((position, end))
            if end >= text_length:
                break

            # 下一个片段的起点回退 chunk_overlap，并跳过分隔符等空白
            next_position = end - self.chunk_overlap
            if next_position <= position:
                next_position = end
            while next_position < text_length and text[next_position].isspace():
                next_position += 1
            position = max(next_position, position + 1)

        return spans

    @staticmethod
    def _align_to_paragraph(text: str, start: int, limit: int) -> int:
        """把切点收缩到窗口内最后一个段落分隔符处；没有分隔符则按窗口硬切。"""
        if limit >= len(text):
            return limit
        boundary: int | None = None
        for match in _PARAGRAPH_SEPARATOR.finditer(text[start:limit]):
            boundary = start + match.start()
        if boundary is None or boundary <= start:
            return limit
        return boundary

    @staticmethod
    def _extract_heading_path(unit: DocumentUnit) -> list[str]:
        """从 unit 的 metadata_json 里取出标题文本序列（无标题时为空列表）。"""
        metadata = unit.metadata_json or {}
        headings = metadata.get("headings") or []
        return [text for heading in headings if (text := heading.get("text"))]
