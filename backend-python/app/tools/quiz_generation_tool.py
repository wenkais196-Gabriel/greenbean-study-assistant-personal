"""
Quiz Generation Tool for Agent learning assistance.

⚠️ **待办**：提示词应集中到 `app/prompts/`（该目录已有 analysis / chat / classification / todo），
目前 quiz 的提示词仍内联在本文件里。
"""

import json
from typing import Any, Dict, Optional

DEFAULT_QUIZ_COUNT = 3


class QuizGenerationTool:
    name: str = "quiz_generation_tool"
    description: str = "Generates interactive study quizzes from course context."

    def __init__(self, provider: Optional[Any] = None):
        self.provider = provider

    async def run(
        self,
        context_text: str,
        num_questions: int = DEFAULT_QUIZ_COUNT,
    ) -> Dict[str, Any]:
        if not context_text or not context_text.strip():
            raise ValueError("context_text cannot be empty")
        if num_questions <= 0:
            raise ValueError("num_questions must be positive")

        if not self.provider:
            return {"success": False, "error": "Provider not configured"}

        response = await self.provider.chat_completion(
            messages=[
                {
                    "role": "user",
                    "content": f"Generate {num_questions} quizzes for: {context_text}",
                }
            ]
        )
        try:
            parsed = json.loads(response.content)
        except (json.JSONDecodeError, TypeError) as exc:
            return {"success": False, "error": f"Provider returned invalid JSON: {exc}"}
        return {"success": True, "data": parsed}
