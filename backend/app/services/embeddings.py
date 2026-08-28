"""
Embeddings service.

Generates 768-dimensional vectors from code chunks using:
- Ollama + nomic-embed-text for local development
- Gemini gemini-embedding-001 for production

The provider is selected through EMBEDDING_PROVIDER.

Code chunks use RETRIEVAL_DOCUMENT embeddings.
User queries use RETRIEVAL_QUERY embeddings.

Both are generated in the same Gemini embedding space when
EMBEDDING_PROVIDER=gemini.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.config import settings
from app.services.ast_walker import FunctionInfo

logger = logging.getLogger(__name__)

# Supabase vector column and retrieval function expect 768 dimensions.
EMBEDDING_DIM = 768

GEMINI_EMBEDDING_MODEL = "gemini-embedding-001"


@dataclass
class CodeChunk:
    """A single embeddable unit ready for storage in code_chunks."""

    file_path: str
    function_name: str | None
    chunk_type: str  # function | class | module
    start_line: int
    end_line: int
    content: str
    embedding: list[float]  # 768-dim vector


async def embed_functions(
    functions: list[FunctionInfo],
    repo_id: str,
) -> list[CodeChunk]:
    """
    Generate embeddings for all extracted functions.

    Code chunks are embedded as retrieval documents.
    """

    if not functions:
        return []

    embedder = _get_embedder()

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

    logger.info(
        "Generated %d embeddings for repo %s",
        len(chunks),
        repo_id,
    )

    return chunks


def _format_for_embedding(fn: FunctionInfo) -> str:
    """
    Format a function for the embedding model.

    Include structural metadata so retrieval can use:
    - file path
    - function name
    - programming language
    - source code
    """

    header = (
        f"File: {fn.file_path}\n"
        f"Function: {fn.function_name}\n"
        f"Language: {fn.language}\n\n"
    )

    return header + fn.content[:2000]


# ---------------------------------------------------------------------------
# Embedder implementations
# ---------------------------------------------------------------------------


class OllamaEmbedder:
    """Calls Ollama's /api/embeddings endpoint."""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    async def embed_batch(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        import httpx

        vectors: list[list[float]] = []

        async with httpx.AsyncClient(timeout=60) as client:
            # Ollama doesn't support batch embeddings in this endpoint.
            for text in texts:
                resp = await client.post(
                    f"{self._base_url}/api/embeddings",
                    json={
                        "model": "nomic-embed-text",
                        "prompt": text,
                    },
                )

                resp.raise_for_status()

                data = resp.json()
                vector = data["embedding"]

                if len(vector) != EMBEDDING_DIM:
                    raise ValueError(
                        f"Ollama returned {len(vector)} dimensions; "
                        f"expected {EMBEDDING_DIM}."
                    )

                vectors.append(vector)

        return vectors


class GeminiEmbedder:
    """
    Calls Google's Gemini embedding API.

    gemini-embedding-001 supports retrieval-specific task types
    and configurable output dimensionality.
    """

    def __init__(
        self,
        api_key: str,
    ) -> None:
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY is required when "
                "EMBEDDING_PROVIDER='gemini'."
            )

        from google import genai

        self._client = genai.Client(api_key=api_key)

    async def embed_batch(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        """
        Embed code chunks as retrieval documents.
        """

        result = await self._client.aio.models.embed_content(
            model=GEMINI_EMBEDDING_MODEL,
            contents=texts,
            config={
                "task_type": "RETRIEVAL_DOCUMENT",
                "output_dimensionality": EMBEDDING_DIM,
            },
        )

        if not result.embeddings:
            raise ValueError(
                "Gemini returned no embeddings."
            )

        vectors = []

        for embedding in result.embeddings:
            if not embedding.values:
                raise ValueError(
                    "Gemini returned an empty embedding."
                )

            vector = list(embedding.values)

            if len(vector) != EMBEDDING_DIM:
                raise ValueError(
                    f"Gemini returned {len(vector)} dimensions; "
                    f"expected {EMBEDDING_DIM}."
                )

            vectors.append(vector)

        if len(vectors) != len(texts):
            raise ValueError(
                f"Gemini returned {len(vectors)} embeddings for "
                f"{len(texts)} inputs."
            )

        return vectors

    async def embed_query(
        self,
        text: str,
    ) -> list[float]:
        """
        Embed a user query for retrieval.

        CODE_RETRIEVAL_QUERY is specifically designed for natural-language
        queries against code retrieval systems.
        """

        result = await self._client.aio.models.embed_content(
            model=GEMINI_EMBEDDING_MODEL,
            contents=text,
            config={
                "task_type": "CODE_RETRIEVAL_QUERY",
                "output_dimensionality": EMBEDDING_DIM,
            },
        )

        if not result.embeddings:
            raise ValueError(
                "Gemini returned no query embedding."
            )

        embedding = result.embeddings[0]

        if not embedding.values:
            raise ValueError(
                "Gemini returned an empty query embedding."
            )

        vector = list(embedding.values)

        if len(vector) != EMBEDDING_DIM:
            raise ValueError(
                f"Gemini returned {len(vector)} dimensions; "
                f"expected {EMBEDDING_DIM}."
            )

        return vector


class NoOpEmbedder:
    """Returns zero vectors for development/testing only."""

    async def embed_batch(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        return [[0.0] * EMBEDDING_DIM for _ in texts]


# ---------------------------------------------------------------------------
# Provider selection
# ---------------------------------------------------------------------------


def _get_embedder():
    """
    Single source of truth for embedding provider selection.
    """

    provider = settings.embedding_provider.lower()

    if provider == "ollama":
        return OllamaEmbedder(
            base_url=settings.ollama_base_url,
        )

    if provider == "gemini":
        return GeminiEmbedder(
            api_key=settings.gemini_api_key,
        )

    if provider == "noop":
        return NoOpEmbedder()

    logger.warning(
        "Unknown embedding provider %r — using zero embeddings",
        provider,
    )

    return NoOpEmbedder()


class EmbeddingServiceError(Exception):
    """
    Raised when a live query embedding cannot be generated.
    """


async def embed_query(text: str) -> list[float]:
    """
    Generate a single embedding for a user's chat query.

    Query and stored document embeddings must come from the same
    embedding model/space.
    """

    embedder = _get_embedder()

    if isinstance(embedder, NoOpEmbedder):
        raise EmbeddingServiceError(
            f"EMBEDDING_PROVIDER='{settings.embedding_provider}' "
            "does not provide real embeddings."
        )

    try:
        # Gemini has a dedicated query task type.
        if isinstance(embedder, GeminiEmbedder):
            vector = await embedder.embed_query(text)

        else:
            vectors = await embedder.embed_batch([text])

            if not vectors:
                raise ValueError(
                    "Embedding provider returned no vectors."
                )

            vector = vectors[0]

    except Exception as exc:
        logger.warning(
            "embed_query() failed (provider=%s): %s",
            settings.embedding_provider,
            exc,
        )

        raise EmbeddingServiceError(
            f"Failed to embed query: {exc}"
        ) from exc

    if len(vector) != EMBEDDING_DIM:
        raise EmbeddingServiceError(
            f"Embedding provider returned {len(vector)} dimensions; "
            f"expected {EMBEDDING_DIM}."
        )

    return vector