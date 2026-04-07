from typing import Optional, List, Dict, Any
from openai import AsyncOpenAI

from .base import BaseLLMProvider


class OpenAIProvider(BaseLLMProvider):
    def __init__(self, api_key: str, default_model: str):
        self.client = AsyncOpenAI(api_key=api_key)
        self.default_model = default_model

    async def create(
        self,
        instructions: Optional[str] = None,
        input: Optional[Any] = None,
        *,
        model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        response = await self.client.responses.create(
            model=model or self.default_model,
            instructions=instructions,
            input=input,
            tools=tools,
            tool_choice=tool_choice,
            **kwargs
        )

        return response.output if tools else response.output_text
