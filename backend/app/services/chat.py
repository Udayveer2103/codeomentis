"""
Chat/RAG orchestration.

Owns all chat-domain logic: repo validation, conversation history
retrieval (server is the source of truth, per Decision 2), query
embedding, vector retrieval via match_chunks(), bounded context
construction, prompt building, streaming generation, and persistence to
chat_messages. This module is the single entry point routers/chat.py
calls into.

Failure handling has no deterministic fallback (unlike walkthrough) — on
validation, embedding, or LLM failure, this module yields a structured
ErrorEvent and terminates the generator cleanly. It never raises past its
own boundary; routers/chat.py can treat the event stream as always
well-formed.

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

async def handle_chat_message(repo_id: str, user_id: str, user_message: str):
    """
    Full RAG turn: validate repo -> persist user message -> retrieve
    history -> embed query -> retrieve chunks -> emit sources -> build
    context/prompt -> stream response -> persist assistant message (only
    on full success) -> Done.

    Yields ChatEvent instances. Always terminates the generator itself
    (never raises past this function) — callers can iterate without a
    try/except for validation/LLM/embedding errors specifically, though
    they should still guard against truly unexpected exceptions
    defensively.
    """
    supabase = get_supabase_client()

    validation_error = _validate_repo(supabase, repo_id, user_id)
    if validation_error:
        yield ErrorEvent(message=validation_error)
        return

    # The user's message is saved only after validation passes — avoids
    # writing a chat_messages row for a repo that doesn't exist or isn't
    # accessible to this user.
    _save_message(supabase, repo_id, user_id, "user", user_message)

    history = _get_recent_history(supabase, repo_id, user_id)

    try:
        query_embedding = await embed_query(user_message)
    except EmbeddingServiceError as exc:
        logger.warning("Chat embedding failed for repo %s: %s", repo_id, exc)
        yield ErrorEvent(
            message="Sorry, I couldn't process your question. Please try again."
        )
        return

    chunks = _retrieve_chunks(supabase, repo_id, query_embedding)

    yield SourcesEvent(sources=[_to_source_metadata(c) for c in chunks])

    context = _build_context(chunks)
    system_prompt, user_prompt = _build_prompt(user_message, context, history)

    accumulated = ""
    try:
        async for token in stream_text(user_prompt, system=system_prompt):
            accumulated += token
            yield TokenEvent(text=token)
    except LLMServiceError as exc:
        logger.warning("Chat generation failed for repo %s: %s", repo_id, exc)
        yield ErrorEvent(
            message="Sorry, I couldn't generate a response. Please try again."
        )
        # Deliberately not persisting `accumulated` — an incomplete,
        # truncated answer in history would confuse the next turn (the
        # LLM would see its own cut-off response as prior context).
        return

    _save_message(supabase, repo_id, user_id, "assistant", accumulated)

    yield DoneEvent()


# ---------------------------------------------------------------------------
# Repo validation
# ---------------------------------------------------------------------------

def _validate_repo(supabase, repo_id: str, user_id: str) -> str | None:
    """
    Returns a user-facing error message if the repo can't be chatted
    with, or None if validation passes. Checks existence, ownership, and
    readiness — mirrors the checks routers/walkthrough.py and presumably
    routers/heatmap.py perform, but placed here too so this service is
    safe to call from any future caller, not only an HTTP request that
    already validated upstream.
    """
    result = (
        supabase.table("repos")
        .select("id,user_id,status")
        .eq("id", repo_id)
        .execute()
    )
    rows = result.data or []
    if not rows:
        return "Repository not found."

    repo = rows[0]

    if repo["user_id"] != user_id:
        return "You do not have access to this repository."

    if repo["status"] != "ready":
        return f"Repository is not ready yet (status: {repo['status']})."

    return None


# ---------------------------------------------------------------------------
# History retrieval (Decision 2: server is the source of truth)
# ---------------------------------------------------------------------------

def _get_recent_history(supabase, repo_id: str, user_id: str) -> list[dict]:
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
    return list(reversed(rows))  # oldest-first for prompt construction


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def _retrieve_chunks(
    supabase,
    repo_id: str,
    query_embedding: list[float],
) -> list[RetrievedChunk]:
    result = supabase.rpc("match_chunks", {
        "query_embedding": query_embedding,
        "match_repo_id": repo_id,
        "match_count": settings.chat_match_count,
    }).execute()

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
    Water-filling allocation of the character budget across chunks.

    Rather than giving every chunk an equal share regardless of size
    (wasteful for small chunks, unnecessarily truncating large ones),
    this processes chunks smallest-first: a chunk that fits within its
    even share consumes only what it actually needs, and the leftover is
    redistributed across the remaining (larger) chunks. No chunk is
    truncated more than the overall budget actually requires.

    Returns {chunk_id: allocated_chars}.
    """
    n = len(chunks)
    if n == 0:
        return {}

    remaining_budget = max(total_budget, MIN_CHARS_PER_CHUNK * n)
    remaining_count = n
    allocation: dict[str, int] = {}

    for c in sorted(chunks, key=lambda c: len(c.content)):
        even_share = max(MIN_CHARS_PER_CHUNK, remaining_budget // remaining_count)
        given = min(len(c.content), even_share)
        allocation[c.chunk_id] = given
        remaining_budget -= given
        remaining_count -= 1

    return allocation


def _build_context(chunks: list[RetrievedChunk]) -> str:
    """
    Builds the code-context block for the prompt, bounded by
    settings.chat_context_char_budget via water-filling allocation (see
    _allocate_budget) rather than a flat even split — smaller chunks
    aren't truncated below their actual size, and larger chunks get to
    use the budget smaller chunks didn't need.
    """
    if not chunks:
        return "No relevant code context was found for this question."

    allocation = _allocate_budget(chunks, settings.chat_context_char_budget)

    parts = []
    for c in chunks:  # preserve original relevance-ranked order in output
        location = c.file_path
        if c.function_name:
            location += f"::{c.function_name}"
        if c.start_line is not None and c.end_line is not None:
            location += f" (lines {c.start_line}-{c.end_line})"

        snippet = c.content[: allocation[c.chunk_id]]
        parts.append(f"[{location}]\n{snippet}")

    return "\n\n".join(parts)


def _build_prompt(
    user_message: str,
    context: str,
    history: list[dict],
) -> tuple[str, str]:
    """
    Returns (system_prompt, user_prompt). All chat-specific prompt
    engineering lives here — llm.py never sees any of this.
    """
    system_prompt = (
        "You are a helpful assistant answering questions about a specific "
        "codebase, using only the provided code context. If the context "
        "doesn't contain enough information to answer confidently, say so "
        "rather than guessing. Keep answers concise and reference specific "
        "files/functions from the context where relevant."
    )

    history_text = ""
    if history:
        history_lines = [f"{m['role']}: {m['content']}" for m in history]
        history_text = "Conversation so far:\n" + "\n".join(history_lines) + "\n\n"

    user_prompt = (
        f"{history_text}"
        f"Relevant code context:\n{context}\n\n"
        f"Question: {user_message}"
    )

    return system_prompt, user_prompt


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _save_message(supabase, repo_id: str, user_id: str, role: str, content: str) -> None:
    supabase.table("chat_messages").insert({
        "repo_id": repo_id,
        "user_id": user_id,
        "role": role,
        "content": content,
    }).execute()