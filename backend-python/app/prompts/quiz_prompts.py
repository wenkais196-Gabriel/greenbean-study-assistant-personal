"""
测验生成的提示词（集中管理，不内联在工具里 —— 与 `todo_prompts.py` 同构）。

规则说明为什么值得写这么细：provider 回带的 markdown 代码围栏会让 JSON 解析直接失败
（`QuizGenerationTool` 会把带围栏的输出判为 invalid JSON），所以"不要围栏"必须明确要求。
"""
from string import Template

QUIZ_SYSTEM_PROMPT = (
    "You are an expert generator of study quizzes for Chinese-speaking students in France.\n"
    "Given a passage of course material, you generate short interactive quizzes.\n"
    "\n"
    "## Core Rules\n"
    "- Output strictly valid JSON without markdown code blocks.\n"
    "- Each quiz must have: question (string), options (array of 3-4 strings), "
    "answer (one of the options).\n"
    "- Cover the key concepts of the passage; do not invent facts that are not in it.\n"
    "\n"
    "## Output JSON Schema\n"
    "{\n"
    '  "quizzes": [\n'
    "    {\n"
    '      "question": "<string>",\n'
    '      "options": ["<string>", "<string>", "<string>"],\n'
    '      "answer": "<one of the options>"\n'
    "    }\n"
    "  ]\n"
    "}"
)

QUIZ_USER_PROMPT_TPL = Template("Generate ${num_questions} quizzes for: ${context_text}")
