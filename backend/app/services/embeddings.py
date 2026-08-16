"""
Embedding provider abstraction for CodeForge AI (Step 6).

Provides a clean interface to swap embedding backends:
  - MockEmbeddingProvider     : deterministic, offline (default for tests)
  - GrokEmbeddingProvider     : Grok-compatible API (if supported by provider)
  - LocalEmbeddingProvider    : future local model integration
"""
import hashlib
import math
import logging
from abc import ABC, abstractmethod
from typing import List

logger = logging.getLogger("codeforge.embeddings")

EMBEDDING_DIMENSIONS = 1536


class EmbeddingProvider(ABC):
    """Abstract base class for all embedding providers."""

    @abstractmethod
    async def get_embedding(self, text: str) -> List[float]:
        """Generate a single embedding vector for the given text."""
        ...

    @abstractmethod
    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embedding vectors in batch for a list of texts."""
        ...


class MockEmbeddingProvider(EmbeddingProvider):
    """
    Deterministic mock embedding provider.

    Uses SHA-256 of the input text to seed a reproducible pseudo-random
    unit vector. Identical inputs always produce identical vectors.
    Safe for offline use and unit testing.
    """

    def __init__(self, dimensions: int = EMBEDDING_DIMENSIONS):
        self.dimensions = dimensions

    def _text_to_vector(self, text: str) -> List[float]:
        """Convert text to a deterministic unit vector via SHA-256 seeding."""
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        # Seed deterministic floats from the digest bytes
        values: List[float] = []
        for i in range(self.dimensions):
            byte_idx = i % len(digest)
            # Generate a float in [-1, 1] from the byte value
            values.append((digest[byte_idx] / 127.5) - 1.0)
        # Normalize to unit vector (cosine similarity requires unit vectors)
        magnitude = math.sqrt(sum(v * v for v in values)) or 1.0
        return [v / magnitude for v in values]

    async def get_embedding(self, text: str) -> List[float]:
        return self._text_to_vector(text)

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        return [self._text_to_vector(t) for t in texts]


class GrokEmbeddingProvider(EmbeddingProvider):
    """
    Grok-compatible embedding provider.

    NOTE: As of the current Grok API, embeddings may not be available.
    This implementation is a forward-compatible stub. If the Grok API
    supports embeddings, configure EMBEDDING_PROVIDER=grok in .env.
    Falls back to MockEmbeddingProvider if the API call fails.
    """

    def __init__(self, api_key: str, base_url: str, model: str = "text-embedding-ada-002"):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self._fallback = MockEmbeddingProvider()

    async def _call_api(self, texts: List[str]) -> List[List[float]]:
        import httpx
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/embeddings",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"input": texts, "model": self.model},
                )
                response.raise_for_status()
                data = response.json()
                return [item["embedding"] for item in data["data"]]
        except Exception as exc:
            logger.warning(
                "Grok embedding API unavailable (%s); falling back to mock provider.", exc
            )
            return await self._fallback.get_embeddings(texts)

    async def get_embedding(self, text: str) -> List[float]:
        results = await self._call_api([text])
        return results[0]

    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        return await self._call_api(texts)


def get_embedding_provider() -> EmbeddingProvider:
    """
    Factory function that returns the configured embedding provider.

    Reads EMBEDDING_PROVIDER from app settings (defaults to "mock").
    Supported values: "mock", "grok"

    The provider is intentionally decoupled from the AI chat provider —
    embedding models are a separate capability.
    """
    try:
        from app.core.config import settings
        provider_name = getattr(settings, "EMBEDDING_PROVIDER", "mock").lower()
    except Exception:
        provider_name = "mock"

    if provider_name == "grok":
        try:
            from app.core.config import settings
            return GrokEmbeddingProvider(
                api_key=settings.GROK_API_KEY,
                base_url=str(settings.AI_BASE_URL),
            )
        except Exception as exc:
            logger.warning("Could not initialize GrokEmbeddingProvider: %s. Using mock.", exc)

    return MockEmbeddingProvider()
