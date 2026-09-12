"""
Document Retrieval Tool for Agent inspection.

依赖契约：注入的 `document_repository` 需提供 `get_by_id(document_id)`。
生产 `DocumentRepository.get_by_id` 是**同步**方法，所以这里不 `await`（对同步方法 await 会直接报错）。
"""

from typing import Any, Dict, Optional


class DocumentRetrievalTool:
    name: str = "document_retrieval_tool"
    description: str = "Retrieves document metadata and content details by document ID."

    def __init__(self, document_repository: Optional[Any] = None):
        self.document_repository = document_repository

    async def run(self, document_id: str) -> Dict[str, Any]:
        if not document_id or not document_id.strip():
            raise ValueError("document_id cannot be empty")

        if not self.document_repository:
            return {"success": False, "error": "Document repository not configured"}

        doc = self.document_repository.get_by_id(document_id)
        if not doc:
            return {"success": False, "error": "Document not found"}

        return {
            "success": True,
            "data": {
                "id": doc.id,
                "title": getattr(doc, "title", ""),
                "file_type": getattr(doc, "file_type", ""),
            },
        }
