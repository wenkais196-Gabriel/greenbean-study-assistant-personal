"""
上下文构建器：把召回结果补上来源信息，按预算挑选片段，并渲染成可喂给 LLM 的上下文块。

产出的 ContextItem 是将来 citations（引用回溯）的原料，见 planning/09 §4。
⚠️ `top_k` 的命中不会全部进入上下文：`build_within_budget` 会按字符预算裁剪
（见 docs/retrieval-diagnosis.md §3.2 与 docs/specs/us-stage1-retrieval.md AC11/AC12）。
"""
from dataclasses import dataclass

from app.config.settings import CONTEXT_MAX_CHARS
from app.entities import Chunk
from app.rag.retriever import RetrievalHit
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_unit_repository import DocumentUnitRepository


@dataclass(frozen=True)
class ContextItem:
    chunk_id: str
    text: str
    document_id: str
    page_number: int | None
    heading_path: list[str]
    distance: float


@dataclass(frozen=True)
class ContextSelection:
    """预算裁剪的结果：进入上下文的条目 + 被丢弃的片段 + 估算占用的字符数。"""

    items: list[ContextItem]
    dropped_chunk_ids: list[str]
    used_chars: int


class ContextBuilder:
    def __init__(
        self,
        chunk_repository: ChunkRepository,
        unit_repository: DocumentUnitRepository,
    ) -> None:
        self.chunk_repository = chunk_repository
        self.unit_repository = unit_repository

    def build(self, hits: list[RetrievalHit]) -> list[ContextItem]:
        """把命中补全为上下文条目。

        查不到来源的命中会被**跳过**（索引与权威表可能不同步），而不是让整体失败。
        """
        items: list[ContextItem] = []
        for hit in hits:
            chunk = self.chunk_repository.get_by_id(hit.chunk_id)
            if chunk is None:
                continue
            unit = self.unit_repository.get_by_id(chunk.document_unit_id)
            if unit is None:
                continue
            items.append(
                ContextItem(
                    chunk_id=chunk.id,
                    text=chunk.text_content,
                    document_id=unit.document_id,
                    page_number=unit.page_number,
                    heading_path=self._heading_path(chunk),
                    distance=hit.distance,
                )
            )
        return items

    def build_within_budget(
        self,
        hits: list[RetrievalHit],
        *,
        max_chars: int = CONTEXT_MAX_CHARS,
    ) -> ContextSelection:
        """按字符预算挑选进入上下文的片段。

        规则（见 docs/specs/us-stage1-retrieval.md AC11/AC12）：
        - 预算是**软上限**：至少保留 1 条（首条即便超出预算也保留），避免上下文空转；
        - 超预算的片段**整片丢弃**、不截断文本 —— 半截片段会让引用回溯到不完整的内容；
        - 按 `item.text` 的字符数近似累加，不加载 tokenizer（精确 token 预算交给 provider）。

        入参顺序即优先级：调用方应传按距离升序的 hits（Retriever 的输出）。
        """
        if max_chars <= 0:
            raise ValueError(f"max_chars 必须为正整数，当前为 {max_chars}")

        kept: list[ContextItem] = []
        dropped: list[str] = []
        used = 0
        for item in self.build(hits):
            if kept and used + len(item.text) > max_chars:
                dropped.append(item.chunk_id)
                continue
            kept.append(item)
            used += len(item.text)
        return ContextSelection(items=kept, dropped_chunk_ids=dropped, used_chars=used)

    def render(self, items: list[ContextItem]) -> str:
        """渲染成带来源标记的上下文块；来源编号与条目顺序一致，便于把引用映射回 chunk。"""
        blocks: list[str] = []
        for index, item in enumerate(items, start=1):
            source = f"[来源 {index}]"
            if item.page_number is not None:
                source += f" 第 {item.page_number} 页"
            blocks.append(f"{source}\n{item.text}")
        return "\n\n".join(blocks)

    @staticmethod
    def _heading_path(chunk: Chunk) -> list[str]:
        metadata = chunk.metadata_json or {}
        return list(metadata.get("heading_path") or [])
