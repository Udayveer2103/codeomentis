"""
Onboarding Walkthrough generation and caching.

Owns all walkthrough-domain logic: cache freshness (keyed off the existing
repos.updated_at — no new column needed), deterministic reading-order
computation from the call graph, and best-effort LLM description
generation. This module is the single entry point routers/walkthrough.py
calls into; it owns all reads/writes to walkthrough_steps and the
relevant repos/code_chunks/Storage reads.

Reading order and step importance are 100% deterministic (call-graph BFS
+ out-degree ranking). The LLM is only used to turn that deterministic
structure into human-readable titles/descriptions — it never influences
order or importance, and the feature is fully usable with the LLM
completely unavailable (see _generate_descriptions).

Node identification note: call graph nodes are keyed by an opaque
qualified_name (see services/graph_builder.py) whose exact string format
is not assumed anywhere in this module. file_path and function_name are
read directly from node attributes (stored by build_call_graph and
round-tripped through node_link_data/node_link_graph serialisation),
never parsed out of the node ID itself.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

import networkx as nx

from app.db.supabase import get_supabase_client
from app.services.llm import LLMServiceError, generate_text

logger = logging.getLogger(__name__)

MAX_STEPS = 15
MAX_CONTENT_CHARS = 400          # per-function source excerpt sent to the LLM
MAX_TOTAL_PROMPT_CHARS = 6000    # hard ceiling on total prompt size, regardless of repo size


# ---------------------------------------------------------------------------
# Internal dataclasses (never leak past this module's public API)
# ---------------------------------------------------------------------------

@dataclass
class WalkthroughStep:
    """A single deterministic reading-order entry, before LLM enrichment."""
    file_path: str
    function_name: str | None
    node_id: str          # opaque call-graph node key — used only as a lookup key, never parsed
    bfs_level: int
    in_degree: int
    out_degree: int
    reason: str


@dataclass
class WalkthroughResult:
    """Return type of the public API — router converts this to JSON as-is."""
    steps: list[dict] = field(default_factory=list)
    cached: bool = False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def get_or_generate_walkthrough(repo_id: str) -> WalkthroughResult:
    """
    Single entry point for routers/walkthrough.py.

    Returns cached steps if a valid (non-stale) cache exists; otherwise
    generates, persists, and returns a fresh walkthrough. Never raises due
    to LLM unavailability — worst case, returns a fully deterministic
    walkthrough with fallback titles/descriptions.
    """
    supabase = get_supabase_client()

    current_updated_at = _get_repo_updated_at(supabase, repo_id)
    cached_rows = _get_cached_walkthrough(supabase, repo_id)

    if _is_cache_valid(cached_rows, current_updated_at):
        return WalkthroughResult(steps=cached_rows, cached=True)

    rows = await _generate_walkthrough(repo_id)

    if not rows:
        # Empty/disconnected graph — nothing to cache, return empty result.
        return WalkthroughResult(steps=[], cached=False)

    _save_walkthrough(supabase, repo_id, rows, current_updated_at)

    return WalkthroughResult(steps=rows, cached=False)


# ---------------------------------------------------------------------------
# Cache read / freshness check
# ---------------------------------------------------------------------------

def _get_repo_updated_at(supabase, repo_id: str) -> str:
    result = (
        supabase.table("repos")
        .select("updated_at")
        .eq("id", repo_id)
        .single()
        .execute()
    )
    if not result.data:
        raise ValueError(f"Repo {repo_id} not found")
    return result.data["updated_at"]


def _get_cached_walkthrough(supabase, repo_id: str) -> list[dict]:
    result = (
        supabase.table("walkthrough_steps")
        .select("*")
        .eq("repo_id", repo_id)
        .order("step_order")
        .execute()
    )
    return result.data or []


def _is_cache_valid(cached_rows: list[dict], current_updated_at: str) -> bool:
    if not cached_rows:
        return False
    return cached_rows[0]["source_updated_at"] == current_updated_at


# ---------------------------------------------------------------------------
# Generation pipeline
# ---------------------------------------------------------------------------

async def _generate_walkthrough(repo_id: str) -> list[dict]:
    """
    Full pipeline: load graph -> deterministic ordering -> LLM descriptions
    (best-effort) -> plain dict rows ready for persistence.
    """
    graph = _load_call_graph(repo_id)
    steps = _compute_reading_order(graph)

    if not steps:
        logger.warning(
            "No walkthrough steps computed for repo %s (empty/disconnected graph)",
            repo_id,
        )
        return []

    snippets = _load_snippets(repo_id, steps)
    descriptions = await _generate_descriptions(steps, snippets)  # {} on any LLM failure

    rows = []
    for order, step in enumerate(steps):
        desc = descriptions.get(step.node_id, {})
        rows.append({
            "step_order": order,
            "file_path": step.file_path,
            "function_name": step.function_name,
            "title": desc.get("title") or _fallback_title(step),
            "description": desc.get("description") or step.reason,
            "reason": step.reason,
            "in_degree": step.in_degree,
            "out_degree": step.out_degree,
            "bfs_level": step.bfs_level,
        })
    return rows


def _fallback_title(step: WalkthroughStep) -> str:
    if step.function_name:
        return step.function_name
    return step.file_path.rsplit("/", 1)[-1] if step.file_path else "Unknown"


# ---------------------------------------------------------------------------
# Deterministic: call graph loading
# ---------------------------------------------------------------------------

def _load_call_graph(repo_id: str) -> nx.DiGraph:
    """
    Loads and deserialises the call graph from Supabase Storage.

    FIX (verified item #1): supabase-py's storage .download() returns raw
    bytes. Decoding explicitly as UTF-8 before json.loads() rather than
    relying on json.loads()'s implicit bytes-handling, since that implicit
    path is sensitive to BOMs/encoding edge cases if the file was ever
    written by a different code path.
    """
    supabase = get_supabase_client()
    storage_path = f"{repo_id}/call_graph.json"

    raw: bytes = supabase.storage.from_("graphs").download(storage_path)
    data = json.loads(raw.decode("utf-8"))
    return nx.node_link_graph(data, directed=True)


# ---------------------------------------------------------------------------
# Deterministic: reading-order computation
# ---------------------------------------------------------------------------

def _compute_reading_order(graph: nx.DiGraph) -> list[WalkthroughStep]:
    """
    FIX (verified item #3): file_path and function_name are read directly
    from node attributes (graph.nodes[node]["file_path"] /
    ["function_name"]) — these are set in build_call_graph() and survive
    node_link_data/node_link_graph round-tripping. The node ID itself
    (fn.qualified_name in graph_builder.py) is treated as a fully opaque
    key and is never parsed or split.
    """
    if graph.number_of_nodes() == 0:
        return []

    in_deg = dict(graph.in_degree())
    out_deg = dict(graph.out_degree())

    entry_points = [n for n, d in in_deg.items() if d == 0]

    # Fallback: if every node has an incoming edge (fully cyclic / no clear
    # entry), treat the highest out-degree nodes as synthetic entry points.
    if not entry_points:
        entry_points = sorted(out_deg, key=lambda n: out_deg[n], reverse=True)[:3]

    # Multi-source BFS to assign a level to every reachable node.
    levels: dict[str, int] = {}
    frontier = list(entry_points)
    for n in frontier:
        levels[n] = 0

    level = 0
    while frontier:
        next_frontier = []
        for node in frontier:
            for succ in graph.successors(node):
                if succ not in levels:
                    levels[succ] = level + 1
                    next_frontier.append(succ)
        frontier = next_frontier
        level += 1

    # Any node never reached by BFS (disconnected component) — append at end.
    for n in graph.nodes:
        if n not in levels:
            levels[n] = level

    # Group by level, rank within level by out-degree desc (hub functions
    # first), cap per level so early levels don't crowd out later ones.
    by_level: dict[int, list[str]] = {}
    for node, lvl in levels.items():
        by_level.setdefault(lvl, []).append(node)

    ordered: list[WalkthroughStep] = []
    max_levels = sorted(by_level.keys())
    per_level_cap = max(1, MAX_STEPS // max(1, len(max_levels)))

    for lvl in max_levels:
        nodes_at_level = sorted(
            by_level[lvl],
            key=lambda n: out_deg.get(n, 0),
            reverse=True,
        )[:per_level_cap]

        for node in nodes_at_level:
            node_attrs = graph.nodes[node]
            file_path = node_attrs.get("file_path", "")
            fn_name = node_attrs.get("function_name")
            reason = _build_reason(lvl, in_deg.get(node, 0), out_deg.get(node, 0))
            ordered.append(WalkthroughStep(
                file_path=file_path,
                function_name=fn_name,
                node_id=node,
                bfs_level=lvl,
                in_degree=in_deg.get(node, 0),
                out_degree=out_deg.get(node, 0),
                reason=reason,
            ))

        if len(ordered) >= MAX_STEPS:
            break

    return ordered[:MAX_STEPS]


def _build_reason(level: int, in_degree: int, out_degree: int) -> str:
    if level == 0:
        return "Entry point — not called by any other function in this repo."
    return (
        f"Reached {level} call{'s' if level != 1 else ''} deep from an entry "
        f"point; calls {out_degree} other function"
        f"{'s' if out_degree != 1 else ''}, called by {in_degree}."
    )


# ---------------------------------------------------------------------------
# LLM: source snippet loading
# ---------------------------------------------------------------------------

def _load_snippets(repo_id: str, steps: list[WalkthroughStep]) -> dict[str, str]:
    """
    FIX (verified item #2 + #3): 'content' confirmed as the correct source
    column in code_chunks. Matching is done on (file_path, function_name)
    tuples — the same attributes now read directly from call graph node
    metadata — rather than reconstructing any file_path::function_name
    string that assumed a node-ID format the graph builder doesn't use.
    """
    supabase = get_supabase_client()
    file_paths = list({s.file_path for s in steps})

    result = (
        supabase.table("code_chunks")
        .select("file_path,function_name,content")
        .eq("repo_id", repo_id)
        .in_("file_path", file_paths)
        .execute()
    )

    chunk_lookup: dict[tuple[str, str | None], str] = {}
    for row in result.data or []:
        key = (row["file_path"], row.get("function_name"))
        chunk_lookup[key] = (row.get("content") or "")[:MAX_CONTENT_CHARS]

    snippet_map: dict[str, str] = {}
    for step in steps:
        key = (step.file_path, step.function_name)
        if key in chunk_lookup:
            snippet_map[step.node_id] = chunk_lookup[key]

    return snippet_map


# ---------------------------------------------------------------------------
# LLM: description generation — best-effort, single batched call, bounded size
# ---------------------------------------------------------------------------

async def _generate_descriptions(
    steps: list[WalkthroughStep],
    snippets: dict[str, str],
) -> dict[str, dict]:
    """
    Returns {} on ANY failure (missing provider, network error, malformed
    response) — caller already treats {} as "use deterministic fallback",
    so this function is safe to call unconditionally.
    """
    payload = _build_bounded_payload(steps, snippets)

    system = (
        "You are writing an onboarding walkthrough for developers new to a "
        "codebase. For each item, write a short, plain-English `title` "
        "(3-6 words) and a `description` (1-2 sentences) explaining what "
        "the function does and why it's worth reading at this point in the "
        "onboarding path. Do not invent behaviour not shown in the code. "
        "Respond with ONLY a JSON array, no prose, no markdown fences, "
        "matching this shape: "
        '[{"id": "...", "title": "...", "description": "..."}]'
    )
    prompt = json.dumps(payload)

    try:
        raw = await generate_text(prompt, system=system, temperature=0.3)
        cleaned = (
            raw.strip()
            .removeprefix("```json")
            .removeprefix("```")
            .removesuffix("```")
            .strip()
        )
        parsed = json.loads(cleaned)
        return {item["id"]: item for item in parsed if "id" in item}
    except (LLMServiceError, json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.warning(
            "Walkthrough LLM description generation failed, using "
            "deterministic fallback titles/descriptions instead: %s", exc,
        )
        return {}


def _build_bounded_payload(
    steps: list[WalkthroughStep],
    snippets: dict[str, str],
) -> list[dict]:
    """
    Enforces MAX_TOTAL_PROMPT_CHARS by shrinking per-step code excerpts
    (never dropping steps) so total prompt size stays predictable
    regardless of function length or repo size.
    """
    n = max(1, len(steps))
    per_step_budget = max(50, MAX_TOTAL_PROMPT_CHARS // n)

    payload = []
    for s in steps:
        code = snippets.get(s.node_id, "")
        code = code[: min(MAX_CONTENT_CHARS, per_step_budget)]
        payload.append({
            "id": s.node_id,
            "file_path": s.file_path,
            "function_name": s.function_name,
            "reason": s.reason,
            "code": code,
        })
    return payload


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _save_walkthrough(
    supabase,
    repo_id: str,
    rows: list[dict],
    source_updated_at: str,
) -> None:
    """
    FIX (verified item #4): delete+insert now happens atomically inside a
    single Postgres transaction via the replace_walkthrough_steps() RPC
    function, rather than as two separate .table() calls. A failed insert
    can no longer leave the cache empty — Postgres rolls back the whole
    operation and the previous rows (if any) remain untouched.
    """
    for row in rows:
        row["repo_id"] = repo_id
        row["source_updated_at"] = source_updated_at

    supabase.rpc("replace_walkthrough_steps", {
        "p_repo_id": repo_id,
        "p_rows": rows,
    }).execute()