"""
上下文构建器：把召回结果补上来源信息，并渲染成可喂给 LLM 的上下文块。

产出的 ContextItem 是将来 citations（引用回溯）的原料，见 planning/09 §4。
"""
from dataclasses import dataclass

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
