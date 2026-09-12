"""
Embedding 服务：把文本转成语义向量。

- 模型选型见 planning/08 §2.2（fastembed + 多语言模型，本地推理、离线可用）
- 已知张力（模型的 128 token 序列上限 vs chunk_size 800 字符）见
  docs/specs/us-stage1-embedding.md §12，需靠评测用数据解决
- 本服务只负责"文本 → 向量"，不碰持久化
"""
from typing import Callable, Protocol

from fastembed import TextEmbedding

from app.config.settings import EMBEDDING_DIMENSION, EMBEDDING_MODEL, MAX_EMBED_CHARS
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
    ) -> None:
        self.model_name = model_name
        self.dimension = dimension
        self.max_chars = max_chars
        self._model_factory = model_factory
        self._model: EmbeddingModel | None = None

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """把一批文本转成向量。空列表直接返回空结果，**不加载模型**。"""
        if not texts:
            return []

        prepared = [self._prepare(text) for text in texts]
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

    def embed_query(self, text: str) -> list[float]:
        """把单条查询转成向量（与批量接口对同一文本的结果一致）。"""
        return self.embed_texts([text])[0]

    def _get_model(self) -> EmbeddingModel:
        """懒加载模型：首次调用时构造，之后复用同一实例。"""
        if self._model is None:
            self._model = self._model_factory(self.model_name)
        return self._model

    def _prepare(self, text: str) -> str:
        """按配置上限截断超长文本。"""
        return text[: self.max_chars]
