"""
Architecture summarizer — turns ArchitectureService's deterministic
output (tech stack, config files, folders, graph stats) into prose,
using the existing shared LLM infrastructure exactly as-is.

Reuses app.services.llm.generate_text() — no new LLM client, no new
provider selection, no new retry/timeout logic. This module owns
only the prompt and the structured-input contract; everything else
is llm.py's responsibility, per its own docstring.

Per llm.py's contract, LLM failure is never fatal here:
generate_architecture_summary() catches LLMServiceError and returns
None. Callers must fall back to showing the deterministic sections
without an AI summary rather than failing the whole page — nothing
in CodeoMentis should hard-depend on the LLM being available.
"""

from __future__ import annotations

import json
import logging

from app.services.llm import LLMServiceError, generate_text

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = """You are writing a short architecture summary for a
software repository, based only on structured data that was already
deterministically extracted from the repository. You are explaining
what has already been discovered, not discovering anything yourself.

Rules:
- Only state facts that are present in the JSON you're given.
- Never invent frameworks, databases, folders, or files that are not
  listed in the input.
- If a field is null or an empty list, omit that category rather
  than guessing a value for it.
- Write 3-5 short paragraphs of plain prose, no headers, no bullet
  lists, no markdown.
- Write for a developer seeing this repository for the first time.
"""


def _build_prompt(architecture_data: dict) -> str:
    payload = json.dumps(architecture_data, indent=2, default=str)

    return (
        "Here is the deterministically extracted architecture data "
        "for a repository:\n\n"
        f"{payload}\n\n"
        "Write the architecture summary described in your "
        "instructions, based only on this data."
    )


async def generate_architecture_summary(architecture_data: dict) -> str | None:
    """
    architecture_data should combine everything ArchitectureService
    has already computed for one repo, e.g.:

    {
        "repository": "owner/name",
        "architecture_pattern": "mvc",
        "tech_stack": {...},          # from repos.tech_stack
        "config_files": [...],        # from _analyze_config()
        "folders": [...],             # from _analyze_folders()
        "graph_summary": {"node_count": 42, "edge_count": 87},
    }

    Returns the generated prose, or None if the LLM call failed.
    Callers must treat None as "no AI summary available this time"
    and continue rendering the deterministic sections regardless.
    """

    prompt = _build_prompt(architecture_data)

    try:
        return await generate_text(
            prompt=prompt,
            system=_SYSTEM_PROMPT,
            temperature=0.2,
        )

    except LLMServiceError as exc:
        logger.warning(
            "Architecture summary generation failed, degrading to "
            "no AI summary: %s",
            exc,
        )
        return None