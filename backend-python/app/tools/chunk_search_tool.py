"""
Chunk Search Tool for Agent retrieval.

依赖契约：注入的 `retriever` 需实现 `search(query, workspace_id, top_k) -> list[dict]`，
同步或异步实现都可以（工具会按需 `await`）。

⚠️ 与生产链路的两处差距（**待办**，接生产前必须先解决）：
1. 生产 `Retriever` 只有 `retrieve(repository, query)` —— 需要一层适配器把它包成上面的协议；
2. `workspace_id` 过滤目前在**数据模型上做不到**：`chunks` 表没有 workspace 列
   （要经 `document_units → document_records` 关联），所以该参数只透传给实现方，本工具不自行过滤。
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
