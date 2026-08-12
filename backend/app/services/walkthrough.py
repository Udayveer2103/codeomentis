"""
Onboarding Walkthrough generation and caching.

Owns all walkthrough-domain logic: cache freshness (keyed off the existing
repos.updated_at — no new column needed), deterministic reading-order
computation from the call graph, role classification, feature grouping,
and best-effort LLM description generation. This module is the single
entry point routers/walkthrough.py calls into; it owns all reads/writes
to walkthrough_steps and the relevant repos/code_chunks/Storage reads.

Reading order and step importance are 100% deterministic (call-graph BFS
+ out-degree ranking, now scoped within a feature group rather than
globally). Role and group_label are also 100% deterministic (path/name
heuristics) — no LLM call is involved in selection, ordering, role, or
grouping. The LLM is only used to turn that deterministic structure into
human-readable titles/descriptions — it never influences order or
importance, and the feature is fully usable with the LLM completely
unavailable (see _generate_descriptions).

called_by / calls are resolved from the same in-memory graph traversal
used for degree computation, but are deliberately NOT persisted to
walkthrough_steps (see _save_walkthrough) — per the approved v2 spec,
this is derived graph information with no established performance need
to store it, so it's computed fresh on every generation and included in
the API response only. A consequence worth being explicit about: a
CACHED response (served straight from walkthrough_steps) will not
include called_by/calls, since those columns don't exist. Only a
freshly-generated response has them. This is the accepted trade-off,
not an oversight.

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
MAX_CONTENT_CHARS = 400  # per-function source excerpt sent to the LLM
MAX_TOTAL_PROMPT_CHARS = 6000  # hard ceiling on total prompt size, regardless of repo size

# Per-group soft cap on step count (replaces the old global per-level cap —
# see _compute_reading_order). Local tunable, matching this file's existing
# pattern (MAX_STEPS etc. above) rather than assuming config.py's real
# contents, which weren't available this session.
MAX_STEPS_PER_GROUP = 5

# Across the WHOLE walkthrough, at most this many Utility-role steps are
# included as individually named steps; the rest are omitted here and are
# expected to be summarised as "and N more utilities" by the frontend
# (Implementation Details layer) rather than emitted as individual steps.
MAX_UTILITY_STEPS = 2

APPLICATION_SHELL_LABEL = "Application Shell"
AUTHENTICATION_GROUP_LABEL = "Authentication"
OTHER_GROUP_LABEL = "Other"
# Groups with fewer members than this get folded into OTHER_GROUP_LABEL
# rather than appearing as a one-item section — EXCEPT the two synthetic,
# role-driven groups below, which stay visible regardless of size (a
# reader expects to see Application Shell / Authentication even if only
# one node qualifies).
MIN_GROUP_SIZE = 2
_GROUPS_EXEMPT_FROM_FOLDING = (APPLICATION_SHELL_LABEL, AUTHENTICATION_GROUP_LABEL)


# ---------------------------------------------------------------------------
# Role taxonomy (Section 4 of the approved spec — six roles for v1)
# ---------------------------------------------------------------------------

ROLE_AUTHENTICATION = "authentication"
ROLE_APPLICATION_SHELL = "application_shell"
ROLE_API = "api"
ROLE_FEATURE = "feature"
ROLE_BUSINESS_LOGIC = "business_logic"
ROLE_UTILITY = "utility"

# Lower number = higher priority (used for group ordering, Section 5).
# Feature and Business Logic intentionally share a priority tier — they're
# distinguished for badging/description purposes on individual steps, not
# for cross-group ordering.
_ROLE_PRIORITY = {
    ROLE_AUTHENTICATION: 1,
    ROLE_APPLICATION_SHELL: 2,
    ROLE_API: 3,
    ROLE_FEATURE: 4,
    ROLE_BUSINESS_LOGIC: 4,
    ROLE_UTILITY: 5,
}

_AUTH_PATH_MARKERS = ("auth", "login", "session", "proxy")
_AUTH_NAME_MARKERS = ("getuser", "login", "signin", "signout", "auth", "proxy", "session")
_UTILITY_PATH_MARKERS = ("utils", "helpers")
_UTILITY_NAMES = ("cn", "clsx", "classnames")
_BUSINESS_PATH_MARKERS = ("lib/", "services/", "server/", "db/", "queries", "repository")
_BUSINESS_NAME_MARKERS = ("validate", "compute", "process", "query", "persist")
_HTTP_VERBS = ("get", "post", "put", "delete", "patch")


def _classify_role(file_path: str, function_name: str | None, in_degree: int, out_degree: int) -> str:
    """
    Deterministic, heuristic-first role classification. Checked in a fixed
    priority order — first match wins (see docstring priority column in
    the approved spec, Section 4).

    Deliberately conservative: falls through to ROLE_FEATURE as the
    default rather than guessing Business Logic from ambiguous signals,
    since a wrong Feature/Business-Logic split is low-cost (same priority
    tier, same default visibility) while a wrong Authentication/Shell/API/
    Utility classification would visibly mislead the ordering or hide a
    step that should be shown.
    """
    path_lower = (file_path or "").lower()
    name_lower = (function_name or "").lower()
    filename = path_lower.rsplit("/", 1)[-1] if path_lower else ""

    # 1. Authentication
    if any(m in path_lower for m in _AUTH_PATH_MARKERS) or any(m in name_lower for m in _AUTH_NAME_MARKERS):
        return ROLE_AUTHENTICATION

    # 2. Application Shell — layout/middleware files, or a TOP-LEVEL page
    #    (app/page.tsx), never a nested feature page.
    is_top_level_page = path_lower in ("app/page.tsx", "page.tsx")
    if filename in ("layout.tsx", "middleware.ts") or is_top_level_page:
        return ROLE_APPLICATION_SHELL

    # 3. API — path under /api/ with an HTTP-verb-named export.
    if "/api/" in path_lower and name_lower in _HTTP_VERBS:
        return ROLE_API

    # 4. Utility — explicit utils/helpers path, known generic utility
    #    names, or a fully isolated leaf (no callers, calls nothing) that
    #    didn't match anything more specific above.
    is_isolated_leaf = in_degree == 0 and out_degree == 0
    if (
        any(m in path_lower for m in _UTILITY_PATH_MARKERS)
        or name_lower in _UTILITY_NAMES
        or is_isolated_leaf
    ):
        return ROLE_UTILITY

    # 5. Business Logic — service/data-access path conventions or a small
    #    set of unambiguous computation verbs.
    if any(m in path_lower for m in _BUSINESS_PATH_MARKERS) or any(m in name_lower for m in _BUSINESS_NAME_MARKERS):
        return ROLE_BUSINESS_LOGIC

    # 6. Feature — default for everything else with real call relationships.
    return ROLE_FEATURE


# ---------------------------------------------------------------------------
# Feature grouping (Section 5 of the approved spec)
# ---------------------------------------------------------------------------

def _normalize_path_for_grouping(file_path: str) -> str:
    """Drops the filename, framework route-groups '(main)', and dynamic
    segments '[matchId]' — these carry no grouping signal."""
    parts = (file_path or "").split("/")
    cleaned = []
    for part in parts[:-1]:  # drop filename
        if part.startswith("(") and part.endswith(")"):
            continue
        if part.startswith("[") and part.endswith("]"):
            continue
        cleaned.append(part)
    return "/".join(cleaned)


def _first_meaningful_segment(normalized_path: str) -> str | None:
    parts = [p for p in normalized_path.split("/") if p and p not in ("app", "api")]
    if not parts:
        return None
    return parts[0].replace("-", " ").replace("_", " ").title()


def _compute_group_label(file_path: str, role: str) -> str:
    """
    Application Shell: unconditional, role-driven (unchanged).

    Authentication: same synthetic-group mechanism, but only as a
    fallback — if the node's path already yields a meaningful
    feature-specific segment (e.g. "app/auth/login/route.ts" -> "Auth"),
    that natural grouping is kept as-is. The synthetic "Authentication"
    label only kicks in for the case that was actually the problem:
    auth-role nodes with no distinct path segment (root-level proxy.ts,
    or a getUser tucked inside layout.tsx) that would otherwise fall
    into the generic "Other" catch-all.
    """
    if role == ROLE_APPLICATION_SHELL:
        return APPLICATION_SHELL_LABEL

    normalized = _normalize_path_for_grouping(file_path)
    segment = _first_meaningful_segment(normalized)
    if segment:
        return segment
    if role == ROLE_AUTHENTICATION:
        return AUTHENTICATION_GROUP_LABEL
    return OTHER_GROUP_LABEL


def _fold_small_groups(by_group: dict[str, list[str]]) -> dict[str, list[str]]:
    """Groups with fewer than MIN_GROUP_SIZE members fold into 'Other'
    rather than appearing as noise in the table of contents — except the
    synthetic role-driven groups (Application Shell, Authentication),
    which stay visible regardless of size."""
    folded: dict[str, list[str]] = {}
    for label, members in by_group.items():
        if label not in _GROUPS_EXEMPT_FROM_FOLDING and len(members) < MIN_GROUP_SIZE:
            folded.setdefault(OTHER_GROUP_LABEL, []).extend(members)
        else:
            folded.setdefault(label, []).extend(members)
    return folded


def _order_groups(by_group: dict[str, list[str]], roles: dict[str, str]) -> list[str]:
    """Application Shell first, then remaining groups ordered by the
    highest-priority role among their members (Section 5, step 6)."""

    def group_priority(label: str) -> int:
        return min((_ROLE_PRIORITY.get(roles[n], 99) for n in by_group[label]), default=99)

    labels = list(by_group.keys())
    shell = [l for l in labels if l == APPLICATION_SHELL_LABEL]
    other_catchall = [l for l in labels if l == OTHER_GROUP_LABEL]
    rest = [l for l in labels if l not in (APPLICATION_SHELL_LABEL, OTHER_GROUP_LABEL)]
    rest_sorted = sorted(rest, key=lambda l: (group_priority(l), l))
    # "Other" always sorts last — it's the deliberate catch-all, not a
    # feature a reader should be steered toward.
    return shell + rest_sorted + other_catchall


# ---------------------------------------------------------------------------
# Internal dataclasses (never leak past this module's public API)
# ---------------------------------------------------------------------------

@dataclass
class WalkthroughStep:
    """A single deterministic reading-order entry, before LLM enrichment."""
    file_path: str
    function_name: str | None
    node_id: str  # opaque call-graph node key — used only as a lookup key, never parsed
    bfs_level: int
    in_degree: int
    out_degree: int
    reason: str
    role: str
    group_label: str


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
    Full pipeline: load graph -> role classification + grouping ->
    within-group deterministic ordering -> LLM descriptions (best-effort,
    group-aware) -> called_by/calls resolution (response-only) -> plain
    dict rows ready for persistence + response.
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
        called_by, calls = _resolve_relationships(graph, step.node_id)
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
            "role": step.role,
            "group_label": step.group_label,
            # Response-only — see module docstring. _save_walkthrough
            # strips these before persistence; there is no DB column.
            "called_by": called_by,
            "calls": calls,
        })
    return rows


def _fallback_title(step: WalkthroughStep) -> str:
    if step.function_name:
        return step.function_name
    return step.file_path.rsplit("/", 1)[-1] if step.file_path else "Unknown"


def _resolve_relationships(graph: nx.DiGraph, node_id: str) -> tuple[list[str], list[str]]:
    """Resolves predecessor/successor node IDs to human-readable names
    (function_name, falling back to file_path) using the same graph
    already loaded for degree/ordering computation. Computed fresh every
    generation — never persisted (see module docstring)."""

    def names(neighbor_ids) -> list[str]:
        resolved = []
        for n in neighbor_ids:
            attrs = graph.nodes.get(n, {})
            resolved.append(attrs.get("function_name") or attrs.get("file_path") or n)
        return resolved

    if node_id not in graph:
        return [], []
    return names(graph.predecessors(node_id)), names(graph.successors(node_id))


# ---------------------------------------------------------------------------
# Deterministic: call graph loading
# ---------------------------------------------------------------------------

def _load_call_graph(repo_id: str) -> nx.DiGraph:
    """
    Loads and deserialises the call graph from Supabase Storage.

    supabase-py's storage .download() returns raw bytes. Decoding
    explicitly as UTF-8 before json.loads() rather than relying on
    json.loads()'s implicit bytes-handling, since that implicit path is
    sensitive to BOMs/encoding edge cases if the file was ever written by
    a different code path.
    """
    supabase = get_supabase_client()
    storage_path = f"{repo_id}/call_graph.json"

    raw: bytes = supabase.storage.from_("graphs").download(storage_path)
    data = json.loads(raw.decode("utf-8"))
    return nx.node_link_graph(data, directed=True)


# ---------------------------------------------------------------------------
# Deterministic: reading-order computation (now role- and group-aware)
# ---------------------------------------------------------------------------

def _compute_reading_order(graph: nx.DiGraph) -> list[WalkthroughStep]:
    """
    file_path and function_name are read directly from node attributes
    (graph.nodes[node]["file_path"] / ["function_name"]) — these are set
    in build_call_graph() and survive node_link_data/node_link_graph
    round-tripping. The node ID itself (fn.qualified_name in
    graph_builder.py) is treated as a fully opaque key and is never
    parsed or split.

    Pipeline (Section 6 of the approved spec):
      1. Compute degrees + a single global BFS-level pass (unchanged
         mechanism from before — still used as the within-group ordering
         signal, just no longer used for a global per-level cap).
      2. Classify every node's role (deterministic, Section 4).
      3. Compute every node's group_label (deterministic, Section 5).
      4. Cap Utility-role nodes globally to MAX_UTILITY_STEPS.
      5. Bucket by group, fold undersized groups into "Other".
      6. Order groups (Application Shell first, then by role priority,
         "Other" last).
      7. Within each group, order by (bfs_level, -out_degree) — the
         original BFS/degree logic, rescoped from "whole repo" to "this
         feature" — and cap at MAX_STEPS_PER_GROUP.
      8. Concatenate in group order, apply MAX_STEPS as a final overall
         ceiling.
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

    # --- Role classification + grouping ------------------------------
    roles: dict[str, str] = {}
    groups: dict[str, str] = {}
    for node in graph.nodes:
        attrs = graph.nodes[node]
        file_path = attrs.get("file_path", "")
        fn_name = attrs.get("function_name")
        r = _classify_role(file_path, fn_name, in_deg.get(node, 0), out_deg.get(node, 0))
        roles[node] = r
        groups[node] = _compute_group_label(file_path, r)

    # --- Cap Utility-role nodes globally, keep the rest as candidates -
    utility_nodes = sorted(
        (n for n in graph.nodes if roles[n] == ROLE_UTILITY),
        key=lambda n: out_deg.get(n, 0),
        reverse=True,
    )
    utility_allow = set(utility_nodes[:MAX_UTILITY_STEPS])
    candidate_nodes = [
        n for n in graph.nodes
        if roles[n] != ROLE_UTILITY or n in utility_allow
    ]

    # --- Bucket by group, fold undersized groups ----------------------
    by_group: dict[str, list[str]] = {}
    for n in candidate_nodes:
        by_group.setdefault(groups[n], []).append(n)
    by_group = _fold_small_groups(by_group)

    # group_label may have changed for folded nodes — keep a corrected
    # per-node lookup consistent with the folded buckets.
    node_group: dict[str, str] = {}
    for label, members in by_group.items():
        for n in members:
            node_group[n] = label

    group_order = _order_groups(by_group, roles)

    # --- Within-group ordering + per-group cap -------------------------
    ordered: list[WalkthroughStep] = []
    for label in group_order:
        members_sorted = sorted(
            by_group[label],
            key=lambda n: (levels.get(n, 0), -out_deg.get(n, 0)),
        )[:MAX_STEPS_PER_GROUP]

        for node in members_sorted:
            attrs = graph.nodes[node]
            file_path = attrs.get("file_path", "")
            fn_name = attrs.get("function_name")
            lvl = levels.get(node, 0)
            reason = _build_reason(lvl, in_deg.get(node, 0), out_deg.get(node, 0))
            ordered.append(WalkthroughStep(
                file_path=file_path,
                function_name=fn_name,
                node_id=node,
                bfs_level=lvl,
                in_degree=in_deg.get(node, 0),
                out_degree=out_deg.get(node, 0),
                reason=reason,
                role=roles[node],
                group_label=node_group.get(node, label),
            ))

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
    'content' confirmed as the correct source column in code_chunks.
    Matching is done on (file_path, function_name) tuples — the same
    attributes read directly from call graph node metadata — rather than
    reconstructing any file_path::function_name string that assumed a
    node-ID format the graph builder doesn't use.
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
# LLM: description generation — best-effort, single batched call, bounded
# size, now group-aware in the PROMPT PAYLOAD only. Output contract is
# UNCHANGED (still a flat [{"id","title","description"}] array), so
# _generate_descriptions' parsing and fail-safe path needed no changes.
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
        "codebase. The items are grouped by feature area (see each item's "
        "`group_label`) and are already in reading order within their "
        "group. For each item, write a short, plain-English `title` "
        "(3-6 words) and a `description` (1-2 sentences) explaining what "
        "the function does and why it matters to this part of the app — "
        "write as if continuing a walkthrough of that feature, not "
        "describing the function in isolation. Do not invent behaviour "
        "not shown in the code. "
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
    regardless of function length or repo size. `steps` is already in
    final group-then-within-group order, so the payload naturally reads
    group-by-group without any extra sorting here.
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
            "group_label": s.group_label,
            "reason": s.reason,
            "code": code,
        })
    return payload


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

# Keys that exist as real columns on walkthrough_steps. called_by/calls are
# deliberately excluded — see module docstring and the migration file
# (no such columns were added, per the approved simplification).
_PERSISTED_ROW_KEYS = (
    "step_order",
    "file_path",
    "function_name",
    "title",
    "description",
    "reason",
    "in_degree",
    "out_degree",
    "bfs_level",
    "role",
    "group_label",
)


def _save_walkthrough(
    supabase,
    repo_id: str,
    rows: list[dict],
    source_updated_at: str,
) -> None:
    """
    Delete+insert happens atomically inside a single Postgres transaction
    via the replace_walkthrough_steps() RPC function, so a failed insert
    can't leave the cache empty — Postgres rolls back the whole operation
    and the previous rows (if any) remain untouched.

    Persists only the fields that have real columns — response-only
    fields (called_by, calls) are stripped here rather than sent to the
    RPC, so the DB payload matches the schema exactly.
    """
    persisted_rows = []
    for row in rows:
        persisted = {k: row[k] for k in _PERSISTED_ROW_KEYS}
        persisted["repo_id"] = repo_id
        persisted["source_updated_at"] = source_updated_at
        persisted_rows.append(persisted)

    supabase.rpc("replace_walkthrough_steps", {
        "p_repo_id": repo_id,
        "p_rows": persisted_rows,
    }).execute()