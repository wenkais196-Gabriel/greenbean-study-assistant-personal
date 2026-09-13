"""
Chunk Search Tool for Agent retrieval.

依赖契约：注入的 `retriever` 需实现 `search(query, workspace_id, top_k) -> list[dict]`，
同步或异步实现都可以（工具会按需 `await`）。

⚠️ 本工具只**透传** `workspace_id`、不自行过滤 —— 过滤是检索实现方的职责。
生产实现见 `app/tools/adapters.py` 的 `ProductionChunkSearcher`（装配走 `app/tools/factory.py`）：
它把 `Retriever` 包成上面的协议，按 workspace 过滤（`chunks` 表没有 workspace 列，
要经 `document_units → document_records` 关联），并**过采样**（vec0 的 k 在过滤前生效）。
"""

import inspect
from typing import Any, Dict, Optional


class ChunkSearchTool:
    name: str = "chunk_search_tool"
    description: str = "Searches for relevant text chunks in a workspace based on a query."

    def __init__(self, retriever: Optional[Any] = None):
        self.retriever = retriever

    async def run(self, query: str, workspace_id: str = "", top_k: int = 5) -> Dict[str, Any]:
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        if not self.retriever:
            return {"success": False, "error": "Retriever not configured"}

        results = self.retriever.search(query=query, workspace_id=workspace_id, top_k=top_k)
        if inspect.isawaitable(results):
            results = await results
        return {"success": True, "data": results}
