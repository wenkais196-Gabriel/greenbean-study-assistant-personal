"""
Section Context Tool for Agent navigation.

依赖契约：注入的 `section_repository` 需提供 `get_by_id(section_id)`。
生产 `SectionRepository.get_by_id` 是**同步**方法，所以这里不 `await`。
"""

from typing import Any, Dict, Optional


class SectionContextTool:
    name: str = "section_context_tool"
    description: str = "Retrieves section hierarchy and context metadata by section ID."

    def __init__(self, section_repository: Optional[Any] = None):
        self.section_repository = section_repository

    async def run(self, section_id: str) -> Dict[str, Any]:
        if not section_id or not section_id.strip():
            raise ValueError("section_id cannot be empty")

        if not self.section_repository:
            return {"success": False, "error": "Section repository not configured"}

        sec = self.section_repository.get_by_id(section_id)
        if not sec:
            return {"success": False, "error": "Section not found"}

        return {
            "success": True,
            "data": {
                "id": sec.id,
                "title": getattr(sec, "title", ""),
            },
        }
