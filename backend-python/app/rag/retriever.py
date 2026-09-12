"""
检索器：把查询嵌入，在本地向量索引里按语义召回片段。

设计取舍见 docs/specs/us-stage1-retrieval.md：
- 距离语义沿用 sqlite-vec 的 vec0 默认度量（**非平方 L2 / 欧氏距离**，越小越相似，0 为完全相同）：
  实测 vec0 v0.1.9 返回的不是平方 L2（与自算平方 L2 偏差 9.906、与自算欧氏距离偏差 0.000001），
  见 docs/retrieval-diagnosis.md §3.4 —— 与原注释相反，故更正；
- 阈值过滤由配置控制，**默认不过滤** —— 阈值必须由评测数据决定，不能凭感觉设；
- 本类只负责召回，组装上下文与渲染是 ContextBuilder 的职责。
"""
from dataclasses import dataclass

from app.config.settings import RETRIEVAL_MAX_DISTANCE, RETRIEVAL_TOP_K
from app.repositories.embedding_repository import EmbeddingRepository
from app.services.embedding_service import EmbeddingService


@dataclass(frozen=True)
class RetrievalHit:
    chunk_id: str
    distance: float


class Retriever:
    def __init__(
        self,
        embedding_service: EmbeddingService,
        *,
        top_k: int = RETRIEVAL_TOP_K,
        max_distance: float | None = RETRIEVAL_MAX_DISTANCE,
    ) -> None:
        if top_k <= 0:
            raise ValueError(f"top_k 必须为正整数，当前为 {top_k}")
        self.embedding_service = embedding_service
        self.top_k = top_k
        self.max_distance = max_distance

    def retrieve(
        self,
        repository: EmbeddingRepository,
        query: str,
    ) -> list[RetrievalHit]:
        """按语义召回最多 top_k 个片段。

        空白查询直接返回空列表，且**不加载模型**。
        """
        if not query.strip():
            return []

        vector = self.embedding_service.embed_query(query)
        rows = repository.search_similar(vector, top_k=self.top_k)
        hits = [RetrievalHit(chunk_id=row[0], distance=row[1]) for row in rows]

        if self.max_distance is not None:
            hits = [hit for hit in hits if hit.distance <= self.max_distance]
        return hits
