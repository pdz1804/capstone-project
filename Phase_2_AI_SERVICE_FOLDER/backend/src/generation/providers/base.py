from typing import Optional, List, Dict, Any
from abc import ABC, abstractmethod


class BaseLLMProvider(ABC):
    """Async interface for any LLM provider."""

    @abstractmethod
    async def create(
        self,
        instructions: Optional[str] = None,
        input: Optional[Any] = None,
        *,
        model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> str:
        """
        - instructions: system/dev instructions
        - input: text or multimodal input blocks
        - model: override model per request (optional)
        - tools: tool calling definitions
        """
        pass
