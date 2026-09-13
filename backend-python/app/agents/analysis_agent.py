import json
from typing import Any, Dict

from app.prompts.analysis_prompts import ANALYSIS_SYSTEM_PROMPT, ANALYSIS_USER_PROMPT_TPL
from app.providers.registry import ProviderRegistry
from app.schemas.analysis_schema import AnalysisOutput


class AnalysisAgent:
    async def generate_analysis(self, document_context: str) -> Dict[str, Any]:
        try:
            provider = ProviderRegistry.get_active()
            response = await provider.chat_completion(
                messages=[
                    {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": ANALYSIS_USER_PROMPT_TPL.substitute(
                            document_context=document_context
                        ),
                    },
                ],
                temperature=0.3,
                response_format={"type": "json_object"},
            )
            raw_content = response.content
            parsed = json.loads(raw_content)

            validated = AnalysisOutput.model_validate(parsed)
            return validated.model_dump()

        except json.JSONDecodeError as e:
            raise RuntimeError("大模型生成的格式不正确，请重试。") from e
        except Exception as e:
            raise e
