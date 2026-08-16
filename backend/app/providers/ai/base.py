from abc import ABC, abstractmethod
from typing import Type, Any, Optional
from pydantic import BaseModel

class AIProvider(ABC):
    """
    Abstract Base Class defining the standard interface for AI models
    within CodeForge AI, allowing easy hot-swapping between Grok,
    OpenAI, Anthropic, or local tools (Ollama).
    """

    @abstractmethod
    async def generate_text(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None, 
        **kwargs: Any
    ) -> str:
        """Generates plain text responses from the model."""
        pass

    @abstractmethod
    async def generate_structured_output(
        self, 
        prompt: str, 
        response_model: Type[BaseModel], 
        system_prompt: Optional[str] = None, 
        **kwargs: Any
    ) -> BaseModel:
        """Generates structured output validated against a Pydantic schema."""
        pass

    @abstractmethod
    async def analyze_code(
        self, 
        code: str, 
        file_path: str, 
        context: Optional[str] = None
    ) -> str:
        """Performs static code review and lists recommendations/bugs."""
        pass

    @abstractmethod
    async def generate_code(
        self, 
        prompt: str, 
        language: str, 
        context: Optional[str] = None
    ) -> str:
        """Generates raw source code block for the requested language."""
        pass
