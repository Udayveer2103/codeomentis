"""
Shared provider-agnostic LLM service.

All feature code (walkthrough, chat/RAG) must call `generate_text()` from
this module rather than importing a provider SDK directly. Adding a new
provider requires only a new branch in `_build_client()` plus an env var
change (LLM_PROVIDER) — no changes to any calling feature code.

LLM_MODEL has no hardcoded default (see app/config.py) — it must be set
explicitly via environment variable, verified against the provider's
current supported-models list. This prevents the project from silently
depending on a model name that gets deprecated/renamed over time.

Only the package for the *configured* provider needs to be installed.
Other provider SDKs are never imported.

Every call is wrapped in a timeout + bounded retry, and every attempt's
duration is logged (success or failure) to aid debugging and future
performance monitoring. If all attempts fail or time out, LLMServiceError
is raised — callers (e.g. walkthrough generation) MUST treat this as
non-fatal and fall back to deterministic output. The LLM is an
enhancement, never a hard dependency for a feature to function.

Scope note: this module is infrastructure only — provider selection,
timeouts, retries, text generation, timing. It contains NO prompt
engineering or feature-specific logic. Prompts, response schemas, and
domain data structures belong in the calling service (e.g.
services/walkthrough.py, services/chat.py).
"""

from __future__ import annotations

import asyncio
import logging
import time
from functools import lru_cache

from langchain_core.messages import HumanMessage, SystemMessage

from app.config import settings

logger = logging.getLogger(__name__)


class LLMServiceError(Exception):
    """
    Raised for ANY LLM failure: missing provider package, missing/invalid
    config, timeout, network error, provider error, or empty response —
    after retries have been exhausted.

    Callers MUST catch this and fall back to deterministic-only output.
    """


@lru_cache(maxsize=1)
def _build_client():
    """
    Builds a LangChain chat model based on settings.llm_provider.
    Cached as a singleton for the process lifetime — switching providers
    requires an env var change + restart (no runtime provider switching).

    Raises LLMServiceError on failure (missing package, missing config).
    Never call directly — go through generate_text().
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


async def generate_text(
    prompt: str,
    system: str | None = None,
    temperature: float = 0.3,
) -> str:
    """
    Single entry point for all LLM text generation in RepoMind.

    Wraps the call in a timeout (settings.llm_timeout_seconds) and retries
    up to settings.llm_max_retries times on timeout or failure, with a
    short backoff between attempts. Every attempt's duration is logged
    regardless of outcome. If every attempt fails, raises
    LLMServiceError — callers must catch this and degrade to
    deterministic-only behavior. Nothing in RepoMind should hard-depend
    on the LLM being available.

    This function is intentionally generic: it takes a plain prompt string
    and returns a plain string. It has no knowledge of walkthroughs, chat,
    or any other feature — all prompt construction and response parsing
    belongs in the calling service.
    """
    total_attempts = 1 + max(0, settings.llm_max_retries)
    last_error: Exception | None = None

    for attempt in range(1, total_attempts + 1):
        start = time.monotonic()

        try:
            base_client = _build_client()
            client = base_client.bind(temperature=temperature)

            messages: list[SystemMessage | HumanMessage] = []
            if system:
                messages.append(SystemMessage(content=system))
            messages.append(HumanMessage(content=prompt))

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
            # Config errors (missing model/key/package) won't be fixed by
            # retrying — fail fast instead of burning retry attempts.
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
            await asyncio.sleep(0.5 * attempt)  # linear backoff: 0.5s, 1s, ...

    raise LLMServiceError(
        f"LLM generation failed after {total_attempts} attempt(s): {last_error}"
    ) from last_error