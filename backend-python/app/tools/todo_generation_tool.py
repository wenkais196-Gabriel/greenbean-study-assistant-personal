"""
Todo Generation Tool for Agent study planning.

提示词来自 `app/prompts/todo_prompts.py`（集中管理，不内联在工具里）。

`workspace_id` 当前不参与生成 —— 生成只需要内容摘要；保留该参数是为了让调用方
传递上下文（**待办**：将来按 workspace 过滤素材时再用）。
"""

import json
from typing import Any, Dict, Optional

from app.prompts.todo_prompts import TODO_SYSTEM_PROMPT, TODO_USER_PROMPT_TPL


class TodoGenerationTool:
    name: str = "todo_generation_tool"
    description: str = "Generates actionable study todo items from course material."

    def __init__(self, provider: Optional[Any] = None):
        self.provider = provider

    async def run(self, content_summary: str, workspace_id: str = "") -> Dict[str, Any]:
        if not content_summary or not content_summary.strip():
            raise ValueError("content_summary cannot be empty")

        if not self.provider:
            return {"success": False, "error": "Provider not configured"}

        response = await self.provider.chat_completion(
            messages=[
                {"role": "system", "content": TODO_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": TODO_USER_PROMPT_TPL.substitute(
                        document_title="",
                        analysis_summary=content_summary,
                        key_concepts="",
                        highlights="",
                    ),
                },
            ]
        )
        try:
            parsed = json.loads(response.content)
        except (json.JSONDecodeError, TypeError) as exc:
            return {"success": False, "error": f"Provider returned invalid JSON: {exc}"}
        return {"success": True, "data": parsed}
