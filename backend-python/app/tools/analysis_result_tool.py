"""
Analysis Result Tool for Agent querying previous AI analyses.

依赖契约：注入的 `analysis_repository` 需提供 `get_by_workspace_id(workspace_id)`（同步）。

⚠️ **待办**：生产 `AnalysisResultRepository` 目前只有 `save` / `get_by_id`，
既没有按 workspace 的查询方法，`analysis_results` 表也没有 workspace 列（要经 document 关联）——
这个工具在补齐仓储层查询之前**接不上生产**。

`section_id` 参数目前不参与查询（保留给将来的按小节过滤）。
"""

from typing import Any, Dict, Optional


class AnalysisResultTool:
    name: str = "analysis_result_tool"
    description: str = "Retrieves stored AI analysis results by workspace or section."

    def __init__(self, analysis_repository: Optional[Any] = None):
        self.analysis_repository = analysis_repository

    async def run(self, workspace_id: str, section_id: Optional[str] = None) -> Dict[str, Any]:
        if not workspace_id or not workspace_id.strip():
            raise ValueError("workspace_id cannot be empty")

        if not self.analysis_repository:
            return {"success": False, "error": "Analysis repository not configured"}

        results = self.analysis_repository.get_by_workspace_id(workspace_id)
        formatted = [
            {"id": item.id, "summary": getattr(item, "summary", "")}
            for item in (results or [])
        ]
        return {"success": True, "data": formatted}
