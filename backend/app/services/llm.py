"""
Shared provider-agnostic LLM service.

All feature code (walkthrough, chat/RAG) must call generate_text() or
stream_text() from this module rather than importing a provider SDK
directly. Adding a new provider requires only a new branch in
_build_client() plus an env var change (LLM_PROVIDER) — no changes to
any calling feature code.

LLM_MODEL has no hardcoded default (see app/config.py) — it must be set
explicitly via environment variable, verified against the provider's
current supported-models list. This prevents the project from silently
depending on a model name that gets deprecated/renamed over time.

Only the package for the *configured* provider needs to be installed.
Other provider SDKs are never imported.

generate_text() wraps the whole call in a timeout + bounded retry.
stream_text() retries only failures before the first token is yielded;
once streaming has begun, a failure raises immediately and is never
retried, since restarting mid-stream would duplicate or replace
already-visible output. Both log attempt duration for debugging/
performance monitoring.

If all attempts fail, LLMServiceError is raised — callers (e.g.
walkthrough/chat generation) MUST treat this as non-fatal for their
feature and degrade or fail gracefully. The LLM is never a hard
dependency for a feature to function.

Scope note: this module is infrastructure only — provider selection,
timeouts, retries, text/token generation, timing. It contains NO prompt
engineering or feature-specific logic. Prompts, response schemas, and
domain data structures belong in the calling service (e.g.
services/walkthrough.py, services/chat.py).
"""

from __future__ import annotations

import asyncio
import logging
import time
from functools import lru_cache
from typing import AsyncGenerator

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from app.config import settings

logger = logging.getLogger(__name__)


class LLMServiceError(Exception):
    """
    Raised for ANY LLM failure: missing provider package, missing/invalid
    config, timeout, network error, provider error, or empty response —
    after retries have been exhausted (generate_text), or immediately on
    any failure once streaming has begun (stream_text).

    Callers MUST catch this and fall back to deterministic-only output,
    or in the streaming case, terminate the stream cleanly.
    """


@lru_cache(maxsize=1)
def _build_client():
    """
    Builds a LangChain chat model based on settings.llm_provider.
    Cached as a singleton for the process lifetime — switching providers
    requires an env var change + restart (no runtime provider switching).

    Raises LLMServiceError on failure (missing package, missing config).
    Never call directly — go through generate_text() or stream_text().
    """
    if not settings.llm_model:
        raise LLMServiceError(
            "LLM_MODEL is not set. Set it explicitly in the environment "
            "to a model currently supported by LLM_PROVIDER — there is no "
            "default, to avoid silently depending on a deprecated model."
        )

    provider = settings.llm_provider.lower()

    if provider == "groq":
        try:
            from langchain_groq import ChatGroq
        except ImportError as exc:
            raise LLMServiceError(
                "LLM_PROVIDER=groq but the 'langchain-groq' package is not "
                "installed. Run: pip install langchain-groq"
            ) from exc

        if not settings.groq_api_key:
            raise LLMServiceError(
                "LLM_PROVIDER=groq but GROQ_API_KEY is not set in the "
                "environment."
            )

        return ChatGroq(
            api_key=settings.groq_api_key,
            model=settings.llm_model,
        )

    if provider == "ollama":
        try:
            from langchain_ollama import ChatOllama
        except ImportError as exc:
            raise LLMServiceError(
                "LLM_PROVIDER=ollama but the 'langchain-ollama' package is "
                "not installed. Run: pip install langchain-ollama"
            ) from exc

        return ChatOllama(
            base_url=settings.ollama_base_url,
            model=settings.llm_model,
        )

    raise LLMServiceError(
        f"Unsupported LLM_PROVIDER '{provider}'. Supported: 'groq', "
        "'ollama'. Add a new branch in app/services/llm.py to support "
        "additional providers (e.g. langchain-openai, langchain-anthropic, "
        "langchain-google-genai) — install only that provider's package "
        "when you do."
    )


def _build_messages(
    prompt: str,
    system: str | None,
) -> list[BaseMessage]:
    """
    Shared message construction for both generate_text() and stream_text(),
    so the two can never silently diverge in how they build the message
    list (e.g. one using SystemMessage, the other reverting to tuples).
    """
    messages: list[BaseMessage] = []
    if system:
        messages.append(SystemMessage(content=system))
    messages.append(HumanMessage(content=prompt))
    return messages


def _get_bound_client(temperature: float):
    """
    Shared client-build + temperature-bind step for both public functions.
    Raises LLMServiceError via _build_client() if the client can't be
    constructed (missing model/key/package) — this always happens before
    any network call, so it's always safe to retry.
    """
    base_client = _build_client()
    return base_client.bind(temperature=temperature)


# ---------------------------------------------------------------------------
# Public API: non-streaming
# ---------------------------------------------------------------------------

async def generate_text(
    prompt: str,
    system: str | None = None,
    temperature: float = 0.3,
) -> str:
    """
    Single entry point for non-streaming LLM text generation in RepoMind.

    Wraps the call in a timeout (settings.llm_timeout_seconds) and retries
    up to settings.llm_max_retries times on timeout or failure, with a
    short backoff between attempts. Every attempt's duration is logged
    regardless of outcome. If every attempt fails, raises
    LLMServiceError — callers must catch this and degrade to
    deterministic-only behavior. Nothing in RepoMind should hard-depend
    on the LLM being available.
    """
    total_attempts = 1 + max(0, settings.llm_max_retries)
    last_error: Exception | None = None

    for attempt in range(1, total_attempts + 1):
        start = time.monotonic()

        try:
            client = _get_bound_client(temperature)
            messages = _build_messages(prompt, system)

            response = await asyncio.wait_for(
                client.ainvoke(messages),
                timeout=settings.llm_timeout_seconds,
            )
            content = (getattr(response, "content", None) or "").strip()
            duration = time.monotonic() - start

            if not content:
                logger.warning(
                    "LLM returned empty response (attempt %d/%d, "
                    "provider=%s, model=%s, duration=%.2fs)",
                    attempt, total_attempts,
                    settings.llm_provider, settings.llm_model, duration,
                )
                raise LLMServiceError("LLM returned an empty response.")

            logger.info(
                "LLM request succeeded (attempt %d/%d, provider=%s, "
                "model=%s, duration=%.2fs)",
                attempt, total_attempts,
                settings.llm_provider, settings.llm_model, duration,
            )
            return content

        except LLMServiceError as exc:
            duration = time.monotonic() - start
            logger.warning(
                "LLM configuration/response error, not retrying "
                "(duration=%.2fs): %s", duration, exc,
            )
            raise

        except asyncio.TimeoutError as exc:
            duration = time.monotonic() - start
            last_error = exc
            logger.warning(
                "LLM request timed out after %.2fs (limit=%.1fs, "
                "attempt %d/%d, provider=%s, model=%s)",
                duration, settings.llm_timeout_seconds,
                attempt, total_attempts,
                settings.llm_provider, settings.llm_model,
            )

        except Exception as exc:
            duration = time.monotonic() - start
            last_error = exc
            logger.warning(
                "LLM generation failed (attempt %d/%d, provider=%s, "
                "model=%s, duration=%.2fs): %s",
                attempt, total_attempts,
                settings.llm_provider, settings.llm_model, duration, exc,
            )

        if attempt < total_attempts:
            await asyncio.sleep(0.5 * attempt)

    raise LLMServiceError(
        f"LLM generation failed after {total_attempts} attempt(s): {last_error}"
    ) from last_error


# ---------------------------------------------------------------------------
# Public API: streaming
# ---------------------------------------------------------------------------

async def stream_text(
    prompt: str,
    system: str | None = None,
    temperature: float = 0.3,
) -> AsyncGenerator[str, None]:
    """
    Provider-agnostic streaming text generation. Yields plain text deltas
    as they arrive — this function has no knowledge of SSE, chat messages,
    or any downstream concept. Callers (e.g. services/chat.py) consume the
    stream and decide how to package each piece.

    Retry behavior differs from generate_text():
      - Failures BEFORE the first token is yielded are retried, same as
        generate_text() (up to settings.llm_max_retries), since nothing
        has been shown to the user yet.
      - Failures AFTER the first token has been yielded are NOT retried.
        Restarting mid-stream would either duplicate already-emitted
        content or silently replace it, both confusing to the user. In
        this case, LLMServiceError is raised immediately and propagates
        to the caller, which must treat it as "stream ended abnormally"
        and stop cleanly rather than retry or restart generation.

    Timeout behavior:
      - settings.llm_timeout_seconds is used as the time-to-first-token
        timeout (part of the retryable phase above).
      - The same value is reused as a STALL timeout between subsequent
        tokens once streaming has begun — if no new token arrives within
        that window, the stream is considered dead and LLMServiceError
        is raised (not retried, per above).

    Raises LLMServiceError if:
      - the client can't be built (missing model/key/package),
      - every pre-first-token attempt times out or fails,
      - the stream stalls or errors after streaming has started.
    """
    total_attempts = 1 + max(0, settings.llm_max_retries)
    last_error: Exception | None = None

    for attempt in range(1, total_attempts + 1):
        start = time.monotonic()
        got_first_token = False

        try:
            client = _get_bound_client(temperature)
            messages = _build_messages(prompt, system)

            stream_iter = client.astream(messages).__aiter__()

            while True:
                try:
                    chunk = await asyncio.wait_for(
                        stream_iter.__anext__(),
                        timeout=settings.llm_timeout_seconds,
                    )
                except StopAsyncIteration:
                    break

                # Be defensive about provider chunk formats.
                # Today ChatGroq and ChatOllama emit string content, but
                # future providers (or future LangChain versions) may emit
                # richer objects.
                content = getattr(chunk, "content", "")

                if isinstance(content, str):
                    text = content
                elif content is None:
                    text = ""
                else:
                    text = str(content)

                if not text:
                    continue

                if not got_first_token:
                    duration = time.monotonic() - start
                    logger.info(
                        "LLM stream: first token received (attempt %d/%d, "
                        "provider=%s, model=%s, time_to_first_token=%.2fs)",
                        attempt, total_attempts,
                        settings.llm_provider, settings.llm_model, duration,
                    )
                    got_first_token = True

                yield text

            total_duration = time.monotonic() - start
            logger.info(
                "LLM stream completed (attempt %d/%d, provider=%s, "
                "model=%s, total_duration=%.2fs)",
                attempt, total_attempts,
                settings.llm_provider, settings.llm_model, total_duration,
            )
            return

        except LLMServiceError:
            raise

        except asyncio.TimeoutError as exc:
            duration = time.monotonic() - start

            if got_first_token:
                logger.warning(
                    "LLM stream stalled after %.2fs of silence mid-stream "
                    "(provider=%s, model=%s) — terminating, not retrying.",
                    settings.llm_timeout_seconds,
                    settings.llm_provider, settings.llm_model,
                )
                raise LLMServiceError(
                    f"LLM stream stalled mid-response: {exc}"
                ) from exc

            last_error = exc
            logger.warning(
                "LLM stream timed out before first token (%.2fs, attempt "
                "%d/%d, provider=%s, model=%s)",
                duration, attempt, total_attempts,
                settings.llm_provider, settings.llm_model,
            )

        except Exception as exc:
            duration = time.monotonic() - start

            if got_first_token:
                logger.warning(
                    "LLM stream failed mid-response after %.2fs (provider=%s, "
                    "model=%s): %s — terminating, not retrying.",
                    duration, settings.llm_provider, settings.llm_model, exc,
                )
                raise LLMServiceError(
                    f"LLM stream failed mid-response: {exc}"
                ) from exc

            last_error = exc
            logger.warning(
                "LLM stream failed before first token (attempt %d/%d, "
                "provider=%s, model=%s, duration=%.2fs): %s",
                attempt, total_attempts,
                settings.llm_provider, settings.llm_model, duration, exc,
            )

        if attempt < total_attempts:
            await asyncio.sleep(0.5 * attempt)

    raise LLMServiceError(
        f"LLM stream failed to start after {total_attempts} attempt(s): {last_error}"
    ) from last_error