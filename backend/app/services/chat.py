"""
Chat/RAG orchestration.

Owns all chat-domain logic: repo validation, conversation history
retrieval (server is the source of truth, per Decision 2), query
embedding, vector retrieval via match_chunks(), bounded context
construction, prompt building, streaming generation, and persistence to
chat_messages. This module is the single entry point routers/chat.py
calls into.

Failure handling has no deterministic fallback (unlike walkthrough) —
on validation, embedding, or LLM failure, this module yields a
structured ErrorEvent and terminates the generator cleanly. It never
raises past its own boundary; routers/chat.py can treat the event stream
as always well-formed.

Two distinct chunk types are used deliberately:
  - RetrievedChunk: full internal representation, includes `content`
    (actual code text) — used only for prompt construction, never sent
    to the frontend.
  - SourceMetadata: frontend-facing subset (no content) — this is what
    SourcesEvent actually carries. Keeping these as separate types makes
    "frontend never receives raw chunk content" a type-level guarantee
    rather than something enforced by remembering to strip a field.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.config import settings
from app.db.supabase import get_supabase_client
from app.services.embeddings import EmbeddingServiceError, embed_query
from app.services.llm import LLMServiceError, stream_text

logger = logging.getLogger(__name__)

# Floor so no chunk gets an unusably tiny slice if the budget is small
# relative to the number of retrieved chunks.
MIN_CHARS_PER_CHUNK = 100


# ---------------------------------------------------------------------------
# Internal chunk representation (includes content — never sent to frontend)
# ---------------------------------------------------------------------------

@dataclass
class RetrievedChunk:
    chunk_id: str
    file_path: str
    function_name: str | None
    similarity: float
    start_line: int | None
    end_line: int | None
    content: str  # actual code text — used for prompt building only


# ---------------------------------------------------------------------------
# Frontend-facing source metadata (no content — structural guarantee)
# ---------------------------------------------------------------------------

@dataclass
class SourceMetadata:
    chunk_id: str
    file_path: str
    function_name: str | None
    similarity: float
    start_line: int | None
    end_line: int | None


def _to_source_metadata(chunk: RetrievedChunk) -> SourceMetadata:
    return SourceMetadata(
        chunk_id=chunk.chunk_id,
        file_path=chunk.file_path,
        function_name=chunk.function_name,
        similarity=chunk.similarity,
        start_line=chunk.start_line,
        end_line=chunk.end_line,
    )


# ---------------------------------------------------------------------------
# Structured event types
# ---------------------------------------------------------------------------

@dataclass
class TokenEvent:
    text: str


@dataclass
class SourcesEvent:
    sources: list[SourceMetadata] = field(default_factory=list)


@dataclass
class ErrorEvent:
    message: str


@dataclass
class DoneEvent:
    pass


ChatEvent = TokenEvent | SourcesEvent | ErrorEvent | DoneEvent


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def handle_chat_message(
    repo_id: str,
    user_id: str,
    user_message: str,
):
    """
    Full RAG turn:

    validate repo
    -> persist user message
    -> retrieve history
    -> embed query
    -> retrieve chunks
    -> emit sources
    -> build context/prompt
    -> stream response
    -> persist assistant message
    -> Done.

    Repository metadata is included in the prompt as authoritative
    metadata. This allows questions such as "what is the name of this
    repo?" to be answered without changing the existing vector RAG flow.

    Yields ChatEvent instances. Always terminates the generator itself.
    """
    supabase = get_supabase_client()

    validation_error, repo_name = _validate_repo(
        supabase,
        repo_id,
        user_id,
    )

    if validation_error:
        yield ErrorEvent(message=validation_error)
        return

    # The user's message is saved only after validation passes.
    _save_message(
        supabase,
        repo_id,
        user_id,
        "user",
        user_message,
    )

    history = _get_recent_history(
        supabase,
        repo_id,
        user_id,
    )

    try:
        query_embedding = await embed_query(user_message)
    except EmbeddingServiceError as exc:
        logger.warning(
            "Chat embedding failed for repo %s: %s",
            repo_id,
            exc,
        )
        yield ErrorEvent(
            message=(
                "Sorry, I couldn't process your question. "
                "Please try again."
            )
        )
        return

    # Existing vector RAG retrieval.
    chunks = _retrieve_chunks(
        supabase,
        repo_id,
        query_embedding,
    )

    # Sources sent to frontend never contain raw code content.
    yield SourcesEvent(
        sources=[
            _to_source_metadata(chunk)
            for chunk in chunks
        ]
    )

    # Keep the existing bounded RAG context.
    code_context = _build_context(chunks)

    # ------------------------------------------------------------------
    # IMPORTANT:
    # Repository metadata is authoritative and separate from retrieved
    # code. This prevents the model from treating the repo name as
    # something it must discover inside a source-code chunk.
    # ------------------------------------------------------------------

    repo_metadata = (
        "AUTHORITATIVE REPOSITORY METADATA\n"
        f"Repository name: {repo_name}\n"
        "END AUTHORITATIVE REPOSITORY METADATA"
    )

    context = (
        f"{repo_metadata}\n\n"
        f"RETRIEVED CODE CONTEXT\n"
        f"{code_context}"
    )

    system_prompt, user_prompt = _build_prompt(
        user_message,
        context,
        history,
    )

    accumulated = ""

    try:
        async for token in stream_text(
            user_prompt,
            system=system_prompt,
        ):
            accumulated += token
            yield TokenEvent(text=token)

    except LLMServiceError as exc:
        logger.warning(
            "Chat generation failed for repo %s: %s",
            repo_id,
            exc,
        )

        yield ErrorEvent(
            message=(
                "Sorry, I couldn't generate a response. "
                "Please try again."
            )
        )

        # Do not persist incomplete responses.
        return

    _save_message(
        supabase,
        repo_id,
        user_id,
        "assistant",
        accumulated,
    )

    yield DoneEvent()


# ---------------------------------------------------------------------------
# Repo validation
# ---------------------------------------------------------------------------

def _validate_repo(
    supabase,
    repo_id: str,
    user_id: str,
) -> tuple[str | None, str | None]:
    """
    Returns:

        (error_message, repo_name)

    Validates repository existence, ownership, and readiness while also
    retrieving the repository name for authoritative chat metadata.
    """
    result = (
        supabase.table("repos")
        .select("id,user_id,status,name")
        .eq("id", repo_id)
        .execute()
    )

    rows = result.data or []

    if not rows:
        return "Repository not found.", None

    repo = rows[0]

    if repo["user_id"] != user_id:
        return (
            "You do not have access to this repository.",
            None,
        )

    if repo["status"] != "ready":
        return (
            f"Repository is not ready yet "
            f"(status: {repo['status']}).",
            None,
        )

    return None, repo["name"]


# ---------------------------------------------------------------------------
# History retrieval (Decision 2: server is the source of truth)
# ---------------------------------------------------------------------------

def _get_recent_history(
    supabase,
    repo_id: str,
    user_id: str,
) -> list[dict]:
    """
    Pulls the last settings.chat_history_limit messages for this repo/user,
    oldest-first, for use as conversation context. The client never
    supplies history — only the new message — per Decision 2.
    """
    result = (
        supabase.table("chat_messages")
        .select("role,content,created_at")
        .eq("repo_id", repo_id)
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(settings.chat_history_limit)
        .execute()
    )

    rows = result.data or []

    return list(reversed(rows))


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def _retrieve_chunks(
    supabase,
    repo_id: str,
    query_embedding: list[float],
) -> list[RetrievedChunk]:
    result = supabase.rpc(
        "match_chunks",
        {
            "query_embedding": query_embedding,
            "match_repo_id": repo_id,
            "match_count": settings.chat_match_count,
        },
    ).execute()

    rows = result.data or []

    return [
        RetrievedChunk(
            chunk_id=row["id"],
            file_path=row["file_path"],
            function_name=row.get("function_name"),
            similarity=row["similarity"],
            start_line=row.get("start_line"),
            end_line=row.get("end_line"),
            content=row.get("content") or "",
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Context + prompt construction
# ---------------------------------------------------------------------------

def _allocate_budget(
    chunks: list[RetrievedChunk],
    total_budget: int,
) -> dict[str, int]:
    """
    Water-filling allocation of the character budget.

    Rather than giving every chunk an equal share regardless of size,
    this processes chunks smallest-first: a chunk that fits within its
    even share consumes only what it actually needs, and the leftover is
    redistributed across the remaining larger chunks.

    Returns:
        {chunk_id: allocated_chars}
    """
    n = len(chunks)

    if n == 0:
        return {}

    remaining_budget = max(
        total_budget,
        MIN_CHARS_PER_CHUNK * n,
    )

    remaining_count = n
    allocation: dict[str, int] = {}

    for chunk in sorted(
        chunks,
        key=lambda c: len(c.content),
    ):
        even_share = max(
            MIN_CHARS_PER_CHUNK,
            remaining_budget // remaining_count,
        )

        given = min(
            len(chunk.content),
            even_share,
        )

        allocation[chunk.chunk_id] = given

        remaining_budget -= given
        remaining_count -= 1

    return allocation


def _build_context(
    chunks: list[RetrievedChunk],
) -> str:
    """
    Builds the code-context block for the prompt, bounded by
    settings.chat_context_char_budget via water-filling allocation.
    """
    if not chunks:
        return "No relevant code context was found for this question."

    allocation = _allocate_budget(
        chunks,
        settings.chat_context_char_budget,
    )

    parts = []

    for chunk in chunks:
        # Preserve original relevance-ranked order in output.
        location = chunk.file_path

        if chunk.function_name:
            location += f"::{chunk.function_name}"

        if (
            chunk.start_line is not None
            and chunk.end_line is not None
        ):
            location += (
                f" (lines {chunk.start_line}-{chunk.end_line})"
            )

        snippet = chunk.content[
            :allocation[chunk.chunk_id]
        ]

        parts.append(
            f"[{location}]\n{snippet}"
        )

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def _build_prompt(
    user_message: str,
    context: str,
    history: list[dict],
) -> tuple[str, str]:
    """
    Returns (system_prompt, user_prompt).

    All chat-specific prompt engineering lives here — llm.py never sees
    any of this.
    """
    system_prompt = (
        "You are a helpful assistant answering questions about a "
        "specific GitHub repository.\n\n"

        "IMPORTANT RULES:\n"
        "1. The section named 'AUTHORITATIVE REPOSITORY METADATA' "
        "contains trusted metadata about the repository.\n"

        "2. If that section contains 'Repository name:', that value "
        "is the repository name. Answer repository-name questions "
        "directly from that value.\n"

        "3. Never say that the repository name is unavailable merely "
        "because the retrieved source-code snippets do not contain "
        "the name.\n"

        "4. Use the retrieved code context for technical questions "
        "about the implementation.\n"

        "5. Do not invent facts that are not supported by the provided "
        "repository metadata or retrieved code context.\n"

        "6. If the provided context genuinely does not contain enough "
        "information to answer a question, say so rather than guessing.\n"

        "7. Keep answers concise and reference specific files/functions "
        "from the retrieved context where relevant."
    )

    history_text = ""

    if history:
        history_lines = [
            f"{message['role']}: {message['content']}"
            for message in history
        ]

        history_text = (
            "Conversation so far:\n"
            + "\n".join(history_lines)
            + "\n\n"
        )

    user_prompt = (
        f"{history_text}"
        f"{context}\n\n"
        f"Question: {user_message}"
    )

    return system_prompt, user_prompt


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _save_message(
    supabase,
    repo_id: str,
    user_id: str,
    role: str,
    content: str,
) -> None:
    supabase.table("chat_messages").insert(
        {
            "repo_id": repo_id,
            "user_id": user_id,
            "role": role,
            "content": content,
        }
    ).execute()