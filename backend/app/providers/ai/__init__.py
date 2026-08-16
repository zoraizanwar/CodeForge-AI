# CodeForge AI providers module
from app.providers.ai.base import AIProvider
from app.providers.ai.grok import GrokProvider


def get_ai_provider() -> AIProvider:
    """Returns configured AI Provider instance (defaulting to GrokProvider)."""
    return GrokProvider()


__all__ = ["AIProvider", "GrokProvider", "get_ai_provider"]
