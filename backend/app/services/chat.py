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
    Full RAG turn:

        validate repo
        -> handle deterministic application-name questions
        -> persist user message
        -> retrieve history
        -> embed query
        -> retrieve chunks
        -> emit sources
        -> build context
        -> stream response
        -> persist assistant response
        -> Done

    The deterministic CodeoMentis handling prevents the LLM/RAG pipeline
    from incorrectly identifying the current application name as RepoMind.

    Yields ChatEvent instances. Always terminates the generator itself
    (never raises past this function) — callers can iterate without a
    try/except for validation/LLM/embedding errors specifically, though
    they should still guard against truly unexpected exceptions
    defensively.
    """

    supabase = get_supabase_client()

    # ------------------------------------------------------------------
    # Repository validation
    # ------------------------------------------------------------------

    validation_error = _validate_repo(
        supabase,
        repo_id,
        user_id,
    )

    if validation_error:
        yield ErrorEvent(message=validation_error)
        return

    # ------------------------------------------------------------------
    # Deterministic application-name handling
    # ------------------------------------------------------------------
    #
    # Application identity is not something that should be inferred from
    # retrieved source-code chunks. For direct name questions, return the
    # authoritative current application name.
    #
    # This does NOT affect normal RAG questions.
    # ------------------------------------------------------------------

    normalized_message = user_message.strip().lower()

    name_question_phrases = (
        "what is the name of this repo",
        "what is this repo called",
        "what is the repository name",
        "name of the repo",
        "name of this repo",
        "name of the repository",
        "name of this repository",
        "what is this project called",
        "what is the project name",
        "what is this repo",
        "what is this repository",
        "what is this project",
        "what is codeomentis",
    )

    if any(
        phrase in normalized_message
        for phrase in name_question_phrases
    ):
        answer = "This repository is CodeoMentis."

        # Persist the user's message exactly like a normal chat turn.
        _save_message(
            supabase,
            repo_id,
            user_id,
            "user",
            user_message,
        )

        # No RAG sources are necessary for authoritative application
        # metadata.
        yield SourcesEvent(sources=[])

        # Use the same token-event mechanism as normal streaming.
        yield TokenEvent(text=answer)

        # Persist the deterministic assistant response.
        _save_message(
            supabase,
            repo_id,
            user_id,
            "assistant",
            answer,
        )

        yield DoneEvent()
        return

    # ------------------------------------------------------------------
    # Normal RAG flow
    # ------------------------------------------------------------------

    # The user's message is saved only after validation passes.
    _save_message(
        supabase,
        repo_id,
        user_id,
        "user",
        user_message,
    )

    # Server remains the source of truth for conversation history.
    history = _get_recent_history(
        supabase,
        repo_id,
        user_id,
    )

    # ------------------------------------------------------------------
    # Query embedding
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Vector retrieval
    # ------------------------------------------------------------------

    chunks = _retrieve_chunks(
        supabase,
        repo_id,
        query_embedding,
    )

    # Only source metadata is sent to the frontend.
    # Raw chunk content stays backend-only.
    yield SourcesEvent(
        sources=[
            _to_source_metadata(chunk)
            for chunk in chunks
        ]
    )

    # ------------------------------------------------------------------
    # Context + prompt construction
    # ------------------------------------------------------------------

    context = _build_context(chunks)

    system_prompt, user_prompt = _build_prompt(
        user_message,
        context,
        history,
    )

    # ------------------------------------------------------------------
    # LLM streaming
    # ------------------------------------------------------------------

    accumulated = ""

    try:
        async for token in stream_text(
            user_prompt,
            system=system_prompt,
        ):
            accumulated += token

            yield TokenEvent(
                text=token,
            )

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

        # Deliberately do not persist incomplete output.
        return

    # ------------------------------------------------------------------
    # Persist successful assistant response
    # ------------------------------------------------------------------

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
) -> str | None:
    """
    Returns a user-facing error message if the repo can't be chatted
    with, or None if validation passes.

    Checks existence, ownership, and readiness.
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
        return (
            f"Repository is not ready yet "
            f"(status: {repo['status']})."
        )

    return None


# ---------------------------------------------------------------------------
# History retrieval
# ---------------------------------------------------------------------------

def _get_recent_history(
    supabase,
    repo_id: str,
    user_id: str,
) -> list[dict]:
    """
    Pulls the last settings.chat_history_limit messages for this
    repo/user, oldest-first, for use as conversation context.

    The client never supplies history — only the new message.
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
    """
    Retrieve the most relevant repository chunks using the existing
    match_chunks Supabase RPC.
    """

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
# Context construction
# ---------------------------------------------------------------------------

def _allocate_budget(
    chunks: list[RetrievedChunk],
    total_budget: int,
) -> dict[str, int]:
    """
    Water-filling allocation of the character budget across chunks.

    Smaller chunks consume only what they actually need, while unused
    budget is redistributed to larger chunks.
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
        key=lambda item: len(item.content),
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

    # Preserve original relevance-ranked order.
    for chunk in chunks:
        location = chunk.file_path

        if chunk.function_name:
            location += f"::{chunk.function_name}"

        if (
            chunk.start_line is not None
            and chunk.end_line is not None
        ):
            location += (
                f" (lines "
                f"{chunk.start_line}-{chunk.end_line})"
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

    All chat-specific prompt engineering lives here.
    llm.py only handles model generation.
    """

    system_prompt = (
        "You are a helpful assistant answering questions about a "
        "specific codebase using the provided repository context. "

        "For technical questions, rely on the retrieved code context. "
        "If the context does not contain enough information to answer "
        "confidently, say so rather than guessing. "

        "The current application name is CodeoMentis. "
        "If the user asks for the current application or project name, "
        "identify it as CodeoMentis. RepoMind is the former project name "
        "and should not be presented as the current application name. "

        "Keep answers concise and reference specific files or functions "
        "from the context where relevant."
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
        f"Relevant code context:\n{context}\n\n"
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
    """
    Persist a chat message.
    """

    supabase.table("chat_messages").insert(
        {
            "repo_id": repo_id,
            "user_id": user_id,
            "role": role,
            "content": content,
        }
    ).execute()