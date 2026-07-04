"""
Embeddings service — generates 768-dim vectors from code chunks using
nomic-embed-text via Ollama (local dev) or falls back to a no-op for
environments without Ollama.

Each function/class is chunked individually rather than using arbitrary
character windows. This preserves semantic units: a chunk is always a
complete function, never half of one.

For production on Render: set EMBEDDING_PROVIDER=ollama and include Ollama
in your Docker image, or switch to a hosted embedding API.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from app.config import settings
from app.services.ast_walker import FunctionInfo

logger = logging.getLogger(__name__)

# nomic-embed-text produces 768-dim vectors
EMBEDDING_DIM = 768


@dataclass
class CodeChunk:
    """A single embeddable unit ready for storage in code_chunks."""
    file_path: str
    function_name: str | None
    chunk_type: str            # function | class | module
    start_line: int
    end_line: int
    content: str
    embedding: list[float]     # 768-dim vector


async def embed_functions(
    functions: list[FunctionInfo],
    repo_id: str,
) -> list[CodeChunk]:
    """
    Generate embeddings for all extracted functions.

    Processes in batches to avoid overwhelming Ollama and to give the
    ingestion pipeline something to report progress on.

    Args:
        functions: All FunctionInfo objects from the repo.
        repo_id:   Used for logging only.

    Returns:
        List of CodeChunk objects ready for Supabase insertion.
    """
    if not functions:
        return []

    provider = settings.embedding_provider.lower()

    if provider == "ollama":
        embedder = OllamaEmbedder(base_url=settings.ollama_base_url)
    else:
        logger.warning(
            "Unknown embedding provider %r — using zero embeddings (development mode)",
            provider,
        )
        embedder = NoOpEmbedder()

    chunks: list[CodeChunk] = []
    batch_size = 20

    for i in range(0, len(functions), batch_size):
        batch = functions[i : i + batch_size]
        texts = [_format_for_embedding(fn) for fn in batch]

        try:
            vectors = await embedder.embed_batch(texts)
        except Exception as exc:
            logger.warning(
                "Embedding batch %d/%d failed (%s) — using zero vectors",
                i // batch_size + 1,
                (len(functions) + batch_size - 1) // batch_size,
                exc,
            )
            vectors = [[0.0] * EMBEDDING_DIM for _ in batch]

        for fn, vector in zip(batch, vectors):
            chunks.append(
                CodeChunk(
                    file_path=fn.file_path,
                    function_name=fn.function_name,
                    chunk_type=fn.chunk_type,
                    start_line=fn.start_line,
                    end_line=fn.end_line,
                    content=fn.content,
                    embedding=vector,
                )
            )

    logger.info("Generated %d embeddings for repo %s", len(chunks), repo_id)
    return chunks


def _format_for_embedding(fn: FunctionInfo) -> str:
    """
    Format a function for the embedding model.

    Prepend a natural-language header so the embedding captures both the
    structural context (file path, function name) and the code content.
    This significantly improves retrieval quality.
    """
    header = (
        f"File: {fn.file_path}\n"
        f"Function: {fn.function_name}\n"
        f"Language: {fn.language}\n\n"
    )
    return header + fn.content[:2000]  # cap at 2000 chars to stay in model context


# ---------------------------------------------------------------------------
# Embedder implementations
# ---------------------------------------------------------------------------

class OllamaEmbedder:
    """Calls Ollama's /api/embeddings endpoint for nomic-embed-text."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        import httpx
        vectors: list[list[float]] = []

        async with httpx.AsyncClient(timeout=60) as client:
            # Ollama doesn't support batch embeddings — serial requests
            for text in texts:
                resp = await client.post(
                    f"{self._base_url}/api/embeddings",
                    json={"model": "nomic-embed-text", "prompt": text},
                )
                resp.raise_for_status()
                data = resp.json()
                vectors.append(data["embedding"])

        return vectors


class NoOpEmbedder:
    """Returns zero vectors — for development without Ollama."""

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * EMBEDDING_DIM for _ in texts]