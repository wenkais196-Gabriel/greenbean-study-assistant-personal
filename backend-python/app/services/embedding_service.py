"""
Embedding 服务：把文本转成语义向量。

- 模型选型见 docs/retrieval-diagnosis.md §3.7 的模型对照（e5-large / 1024 维 / 序列上限 512 token）
- e5 系列要求 query / passage 前缀（settings 的 EMBEDDING_QUERY_PREFIX / EMBEDDING_PASSAGE_PREFIX）：
  前缀在送模型前拼接，**不写进存储文本**，所以 chunk 正文与引用仍是干净原文
- 本服务只负责"文本 → 向量"，不碰持久化
"""
from typing import Callable, Protocol

from fastembed import TextEmbedding

from app.config.settings import (
    EMBEDDING_DIMENSION,
    EMBEDDING_MODEL,
    EMBEDDING_PASSAGE_PREFIX,
    EMBEDDING_QUERY_PREFIX,
    MAX_EMBED_CHARS,
)
from app.repositories.embedding_repository import EmbeddingDimensionError


class EmbeddingModel(Protocol):
    """fastembed 的 TextEmbedding 所需的最小接口（便于测试注入假模型）。"""

    def embed(self, texts, batch_size=None): ...


ModelFactory = Callable[[str], EmbeddingModel]


class EmbeddingService:
    def __init__(
        self,
        model_name: str = EMBEDDING_MODEL,
        *,
        dimension: int = EMBEDDING_DIMENSION,
        max_chars: int = MAX_EMBED_CHARS,
        model_factory: ModelFactory = TextEmbedding,
        query_prefix: str = EMBEDDING_QUERY_PREFIX,
        passage_prefix: str = EMBEDDING_PASSAGE_PREFIX,
    ) -> None:
        self.model_name = model_name
        self.dimension = dimension
        self.max_chars = max_chars
        self.query_prefix = query_prefix
        self.passage_prefix = passage_prefix
        self._model_factory = model_factory
        self._model: EmbeddingModel | None = None

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """把一批**待索引文本**（passage）转成向量。空列表直接返回空结果，**不加载模型**。"""
        if not texts:
            return []
        return self._embed_prepared(
            [self._prepare(self.passage_prefix + text) for text in texts]
        )

    def embed_query(self, text: str) -> list[float]:
        """把单条**查询**转成向量。

        前缀为空时，与批量接口对同一文本的结果一致；e5 这类模型要求 query / passage
        用**不同**前缀，此时二者有意不同 —— 那是模型契约，不是接口不一致。
        """
        return self._embed_prepared([self._prepare(self.query_prefix + text)])[0]

    def _embed_prepared(self, prepared: list[str]) -> list[list[float]]:
        """把已拼好前缀、已截断的文本交给模型，并校验返回数量与维度。"""
        vectors = [list(vector) for vector in self._get_model().embed(prepared)]

        if len(vectors) != len(prepared):
            raise ValueError(
                f"embedding model returned {len(vectors)} vectors for {len(prepared)} texts"
            )
        for vector in vectors:
            if len(vector) != self.dimension:
                raise EmbeddingDimensionError(
                    f"embedding vector dimension must be {self.dimension}, got {len(vector)}"
                )
        return vectors

    def _get_model(self) -> EmbeddingModel:
        """懒加载模型：首次调用时构造，之后复用同一实例。"""
        if self._model is None:
            self._model = self._model_factory(self.model_name)
        return self._model

    def _prepare(self, text: str) -> str:
        """按配置上限截断超长文本。"""
        return text[: self.max_chars]
