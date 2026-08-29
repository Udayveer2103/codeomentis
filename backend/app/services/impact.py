"""
impact.py — CodeoMentis Impact Analyzer service layer

Loads call_graph.json from Supabase Storage, rebuilds it as a
NetworkX DiGraph, reverses it, and runs BFS from the queried node
to find every caller in the blast radius.

Also derives deterministic impact-radius facts from that BFS result,
and uses them (not raw graph nodes) to drive a single structured-
output LLM call producing an AI risk assessment. Results are cached
in impact_ai_cache, keyed by (repo_id, query_node) and invalidated
via analysis_fingerprint + ANALYSIS_VERSION — no time-based expiry.

The AI layer is strictly best-effort: any failure (LLM unavailable,
malformed output, failed validation) falls back to a graph-only
response. Graph analysis itself has no dependency on the AI layer.

Milestone 3: _compute_impact_facts() is now the single source of
truth for deterministic facts — it returns FULL, unbounded data.
_generate_impact_reasoning() is solely responsible for truncating
(MAX_PROMPT_FILES / MAX_PROMPT_NODES) when building the LLM prompt.
The API response reuses the same facts directly; no duplicate
affected-files/entry-point computation exists anywhere in this file.
"""

import hashlib
import json
import logging
from collections import deque
from typing import Any, Literal

import networkx as nx
from fastapi import HTTPException
from pydantic import BaseModel, ValidationError

from app.services.llm import LLMServiceError, generate_text

logger = logging.getLogger(__name__)

# ── Supabase storage / table names ──────────────────────────────────────────
GRAPH_BUCKET = "graphs"
AI_CACHE_TABLE = "impact_ai_cache"

# Bump when the LLM prompt or output schema changes in a way that should
# invalidate previously cached results — no TTL, no cleanup job, existing
# rows simply stop matching and get regenerated on next request.
ANALYSIS_VERSION = "v1"

# Local tunables governing how much of the full, unbounded facts get
# included in the LLM prompt. Kept here rather than in config.py,
# matching this codebase's existing precedent (walkthrough.py's
# MAX_STEPS_PER_GROUP) of keeping feature-local prompt-size caps
# local when config.py's real contents aren't available to extend
# safely. Applied only in _generate_impact_reasoning() — never in
# _compute_impact_facts(), which is always full-fidelity.
MAX_PROMPT_FILES = 30
MAX_PROMPT_NODES = 15


class ImpactAIResult(BaseModel):
    """
    Structured representation of one LLM reasoning result. Constructed
    only from a validated LLM response — never partially populated.
    If construction fails validation, the caller treats it exactly
    like an LLM failure and falls back to a graph-only response.
    """
    ai_summary: str
    safe_to_change: bool
    risk_level: Literal["low", "medium", "high"]
    risk_reasons: list[str]
    possible_regressions: list[str]
    suggested_test_cases: list[str]
    refactoring_advice: str


_IMPACT_SYSTEM_PROMPT = (
    "You are assessing the impact of changing one function in a "
    "software repository. You are given a set of facts already "
    "computed deterministically from the repository's call graph — "
    "total impacted functions, maximum call depth, affected files, "
    "direct vs. indirect caller counts, direct callers, and true "
    "entry points. A high indirect_caller_count relative to "
    "direct_caller_count means the impact is mostly transitive — "
    "changes could propagate through several layers before surfacing. "
    "Do not recompute, second-guess, or contradict these facts — "
    "reason about their implications for risk and safety.\n\n"
    "Rules:\n"
    "- Only reason about the facts provided. Never invent callers, "
    "files, or behavior not present in the input.\n"
    "- risk_level must be exactly one of: low, medium, high.\n"
    "- risk_reasons, possible_regressions, and suggested_test_cases are "
    "each short bullet-style strings (not full paragraphs).\n"
    "- refactoring_advice is 1-3 short sentences.\n"
    "- Respond with ONLY a JSON object, no prose, no markdown fences, "
    "matching this shape exactly: "
    '{"ai_summary": "...", "safe_to_change": true, "risk_level": "low", '
    '"risk_reasons": ["..."], "possible_regressions": ["..."], '
    '"suggested_test_cases": ["..."], "refactoring_advice": "..."}'
)


async def run_impact_analysis(
    supabase,
    repo_id: str,
    query_node: str,
    max_depth: int = 5,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """
    1. Fetch call_graph.json from Supabase Storage
    2. Build DiGraph with networkx
    3. Reverse graph (edges now point FROM caller TO callee)
    4. BFS from query_node up to max_depth
    5. Derive full, unbounded deterministic impact facts (single
       source of truth — used for both the LLM prompt, truncated at
       send-time, and the API response, used in full)
    6. Cache-check (skipped entirely if force_refresh) → generate
       (best-effort, truncates facts internally for the prompt) →
       validate → persist AI reasoning
    7. Reconstruct downstream call chains from facts["entry_points"]
    8. Return node + link lists for D3, AI fields, and Milestone 3
       fields (AI fields are None if the AI layer is unavailable —
       the graph-only result, plus the deterministic fields, is
       always returned)

    force_refresh (Milestone 4): when True, skips
    _load_cached_ai_result() entirely — generation always runs, and
    a successful result overwrites the existing cache row via the
    same _save_ai_result() upsert used for fingerprint/version
    invalidation. Graph loading, BFS, and every deterministic fact
    (facts, affected_files, downstream_call_chain) are completely
    unaffected by this flag — it only changes whether the AI cache
    is consulted before generating. If forced generation fails, the
    existing fail-soft contract applies unchanged: ai_fields stay
    None and _save_ai_result() is never called, so any previously
    valid cached row is left untouched.
    """

    # ── 1. Load graph JSON ────────────────────────────────────────────────
    graph_json, graph_bytes = _load_graph(supabase, repo_id)
    if not graph_json:
        raise HTTPException(
            status_code=404,
            detail="Call graph not found — has this repo been ingested?",
        )

    # ── 2. Build NetworkX graph ───────────────────────────────────────────
    G: nx.DiGraph = nx.node_link_graph(graph_json, directed=True, multigraph=False)

    # ── 3. Validate query node ────────────────────────────────────────────
    if query_node not in G.nodes:
        suggestions = _fuzzy_match(G, query_node, limit=10)
        raise HTTPException(
            status_code=404,
            detail={
                "message": f"Function '{query_node}' not found in call graph",
                "suggestions": suggestions,
            },
        )

    # ── 4. Reverse + BFS ───────────────────────────────────────────────────
    R: nx.DiGraph = G.reverse(copy=True)  # reversed: edge = caller → callee
    bfs_nodes, bfs_links = _bfs(R, query_node, max_depth)

    nodes = []
    for node_id, depth in bfs_nodes.items():
        file_path, _, fn_name = node_id.rpartition("::")
        nodes.append({
            "id": node_id,
            "file_path": file_path or node_id,
            "function_name": fn_name or node_id,
            "depth": depth,
        })
    nodes.sort(key=lambda n: n["depth"])

    links = [{"source": s, "target": t, "depth": d} for s, t, d in bfs_links]

    graph_stats = {
        "total_nodes": G.number_of_nodes(),
        "total_edges": G.number_of_edges(),
    }

    # ── 5. Deterministic facts — FULL, unbounded. Single source of truth. ───
    facts = _compute_impact_facts(query_node, nodes, R)

    # ── 6. AI reasoning: cache-check (unless force_refresh) → generate →
    #        validate → persist ─────────────────────────────────────────────
    ai_fields: dict[str, Any] = {
        "ai_summary": None,
        "safe_to_change": None,
        "risk_level": None,
        "risk_reasons": None,
        "possible_regressions": None,
        "suggested_test_cases": None,
        "refactoring_advice": None,
    }

    fingerprint = _compute_analysis_fingerprint(graph_bytes)

    if force_refresh:
        cached = None
    else:
        cached = _load_cached_ai_result(supabase, repo_id, query_node, fingerprint)

    if cached:
        for key in ai_fields:
            ai_fields[key] = cached.get(key)
    else:
        result = await _generate_impact_reasoning(query_node, facts, graph_stats)
        if result is not None:
            ai_fields.update(result.model_dump())
            _save_ai_result(supabase, repo_id, query_node, fingerprint, result.model_dump())
        # result is None (forced or natural miss + generation failure) →
        # ai_fields stays all-None, _save_ai_result is never called, so
        # any existing valid cache row is left exactly as it was.

    # ── 7. Downstream call chains — reuses facts["entry_points"] directly,
    #        no re-derivation of entry points or affected files. ─────────────
    downstream_call_chain = _compute_downstream_call_chain(
        facts["entry_points"], nodes, links
    )

    # ── 8. Shape response for D3 + AI panel + Milestone 3 fields ────────────
    return {
        "query_node": query_node,
        "nodes": nodes,
        "links": links,
        "total_impacted": facts["total_impacted"],
        "graph_stats": graph_stats,
        "affected_files": facts["affected_files"],
        "downstream_call_chain": downstream_call_chain,
        **ai_fields,
    }


# ── Graph loading / traversal ────────────────────────────────────────────────

def _load_graph(supabase, repo_id: str) -> tuple[dict, bytes] | tuple[None, None]:
    """
    Download call_graph.json from Supabase Storage bucket.

    Returns (parsed_dict, raw_bytes). raw_bytes is required by
    _compute_analysis_fingerprint(), which hashes exactly what
    Storage returned rather than a re-serialization of the parsed
    dict.
    """
    try:
        path = f"{repo_id}/call_graph.json"
        res = supabase.storage.from_(GRAPH_BUCKET).download(path)
        if isinstance(res, (bytes, bytearray)):
            raw = bytes(res)
            return json.loads(raw.decode("utf-8")), raw
        return None, None
    except Exception as e:
        print(f"[impact] Failed to load graph for {repo_id}: {e}")
        return None, None


def _bfs(
    G: nx.DiGraph,
    start: str,
    max_depth: int,
) -> tuple[dict[str, int], list[tuple[str, str, int]]]:
    """
    BFS on the REVERSED graph.
    Returns:
        visited — {node_id: depth}
        edges — [(source, target, depth)] where depth = depth of source node
    """
    visited: dict[str, int] = {start: 0}
    edges: list[tuple[str, str, int]] = []
    queue: deque[tuple[str, int]] = deque([(start, 0)])

    while queue:
        node, depth = queue.popleft()
        if depth >= max_depth:
            continue
        for neighbor in G.successors(node):  # reversed graph: successor = original caller
            if neighbor not in visited:
                visited[neighbor] = depth + 1
                edges.append((neighbor, node, depth + 1))
                queue.append((neighbor, depth + 1))

    return visited, edges


def _fuzzy_match(G: nx.DiGraph, query: str, limit: int = 10) -> list[str]:
    """Return up to `limit` node IDs that contain the query string."""
    q = query.lower()
    return [n for n in G.nodes if q in n.lower()][:limit]


# ── Deterministic fact derivation — single source of truth, FULL/unbounded ──

def _compute_impact_facts(
    query_node: str, nodes: list[dict], R: nx.DiGraph
) -> dict[str, Any]:
    """
    Derives structured, deterministic facts from the already-computed
    BFS result and the already-built reversed graph R — no new graph
    traversal beyond what run_impact_analysis already did.

    Returns FULL, unbounded data — this is the single source of truth
    for both the LLM prompt (truncated only inside
    _generate_impact_reasoning) and the API response (used as-is).
    direct_callers/entry_points entries include "id" so
    _compute_downstream_call_chain() can look them up directly in
    node_by_id/parent_of without recomputing which nodes qualify.

    entry_points is returned in BFS-discovery order, NOT sorted here —
    _generate_impact_reasoning() truncates this exact list/order for
    the LLM prompt, so sorting it would change which entries survive
    truncation on repos with >MAX_PROMPT_NODES entry points. Sorting
    for readability happens only in _compute_downstream_call_chain(),
    on a local copy, after this list has already been used for the
    prompt.
    """
    affected = [n for n in nodes if n["id"] != query_node]

    if not affected:
        return {
            "total_impacted": 0,
            "max_depth": 0,
            "affected_files": [],
            "affected_file_count": 0,
            "direct_callers": [],
            "entry_points": [],
            "direct_caller_count": 0,
            "indirect_caller_count": 0,
        }

    max_depth = max(n["depth"] for n in affected)
    affected_files = sorted({n["file_path"] for n in affected})

    direct_callers = [
        {"id": n["id"], "file_path": n["file_path"], "function_name": n["function_name"]}
        for n in affected if n["depth"] == 1
    ]

    # A node with no callers of its own anywhere in the graph (not just
    # within this BFS) is a true entry point — nothing above it to reach
    # further. Computed directly on R, which run_impact_analysis already
    # builds, so this is a lookup, not a new traversal. This is the ONLY
    # place in the file this filter is applied.
    entry_points = [
        {"id": n["id"], "file_path": n["file_path"], "function_name": n["function_name"]}
        for n in affected if R.out_degree(n["id"]) == 0
    ]

    direct_caller_count = len(direct_callers)
    indirect_caller_count = len(affected) - direct_caller_count

    return {
        "total_impacted": len(affected),
        "max_depth": max_depth,
        "affected_files": affected_files,
        "affected_file_count": len(affected_files),
        "direct_callers": direct_callers,
        "entry_points": entry_points,
        "direct_caller_count": direct_caller_count,
        "indirect_caller_count": indirect_caller_count,
    }


# ── Downstream call chain reconstruction — Milestone 3 ────────────────────────

def _compute_downstream_call_chain(
    entry_points: list[dict], nodes: list[dict], links: list[dict]
) -> list[dict[str, Any]]:
    """
    For each true entry point (supplied from _compute_impact_facts() —
    NOT recomputed here), reconstructs the ordered path of calls from
    that entry point down to query_node via a parent-pointer walk over
    the BFS tree already encoded in `links`. BFS visits each node
    exactly once, so every node has exactly one incoming edge (its
    parent toward query_node) — this makes the walk a simple,
    always-terminating dictionary lookup chain, not a new search.

    Correctness: the walk strictly decreases depth by 1 each step, so
    it always terminates; the only node with no entry in parent_of is
    query_node, so every chain ends there; every adjacent pair in a
    chain is a real BFS edge, since parent_of is built directly from
    `links`.

    entry_points is sorted here via sorted() (a new list, not
    in-place) purely for deterministic output ordering in the API
    response's downstream_call_chain — this does NOT mutate or affect
    the caller's original entry_points list, which
    _generate_impact_reasoning() separately truncates in its own
    BFS-discovery order for the LLM prompt.
    """
    if not entry_points:
        return []

    node_by_id = {n["id"]: n for n in nodes}

    # Each link is (caller=source) -> (callee=target); since BFS visits
    # every node exactly once, each node appears as `source` at most
    # once, so this dict is a well-defined parent pointer toward
    # query_node for every discovered node.
    parent_of: dict[str, str] = {link["source"]: link["target"] for link in links}

    ordered_entry_points = sorted(
        entry_points, key=lambda e: (e["file_path"], e["function_name"])
    )

    chains = []
    for entry in ordered_entry_points:
        chain = [node_by_id[entry["id"]]]
        current = entry["id"]
        while current in parent_of:
            current = parent_of[current]
            chain.append(node_by_id[current])
        chains.append({
            "entry_point": {
                "file_path": entry["file_path"],
                "function_name": entry["function_name"],
            },
            "chain": [
                {
                    "file_path": n["file_path"],
                    "function_name": n["function_name"],
                    "depth": n["depth"],
                }
                for n in chain
            ],
        })
    return chains


# ── AI reasoning cache ────────────────────────────────────────────────────────

def _compute_analysis_fingerprint(graph_json_bytes: bytes) -> str:
    """
    Fingerprint the raw call_graph.json bytes as downloaded from
    Storage. Used to invalidate cached AI results when a repo is
    re-ingested and the underlying analysis content actually changes
    — no time-based expiry, the fingerprint mismatch is the
    invalidation signal.
    """
    return hashlib.sha256(graph_json_bytes).hexdigest()


def _load_cached_ai_result(
    supabase, repo_id: str, query_node: str, analysis_fingerprint: str
) -> dict | None:
    """
    Look up a previously computed AI reasoning result for this
    (repo_id, query_node) pair, valid only if it was generated from
    the current analysis_fingerprint AND the current ANALYSIS_VERSION.
    A mismatch on either is treated as a cache miss, same as no row
    existing. Returns None on miss or on any lookup error, so a cache
    failure degrades to "no AI content" rather than breaking the
    request.
    """
    try:
        res = (
            supabase.table(AI_CACHE_TABLE)
            .select("*")
            .eq("repo_id", repo_id)
            .eq("query_node", query_node)
            .maybe_single()
            .execute()
        )
        row = res.data
        if (
            row
            and row.get("analysis_fingerprint") == analysis_fingerprint
            and row.get("analysis_version") == ANALYSIS_VERSION
        ):
            return row
        return None
    except Exception as e:
        print(f"[impact] AI cache lookup failed for {repo_id}/{query_node}: {e}")
        return None


def _save_ai_result(
    supabase, repo_id: str, query_node: str, analysis_fingerprint: str, ai_fields: dict
) -> None:
    """
    Upsert the AI reasoning result for this (repo_id, query_node) pair,
    stamped with the analysis_fingerprint and ANALYSIS_VERSION it was
    generated from. Upsert rather than insert so re-generation (forced,
    fingerprint-stale, or version-stale) overwrites the existing row
    instead of violating the unique constraint.
    """
    try:
        supabase.table(AI_CACHE_TABLE).upsert(
            {
                "repo_id": repo_id,
                "query_node": query_node,
                "analysis_fingerprint": analysis_fingerprint,
                "analysis_version": ANALYSIS_VERSION,
                **ai_fields,
            },
            on_conflict="repo_id,query_node",
        ).execute()
    except Exception as e:
        print(f"[impact] Failed to save AI cache for {repo_id}/{query_node}: {e}")


async def _generate_impact_reasoning(
    query_node: str, facts: dict, graph_stats: dict
) -> ImpactAIResult | None:
    """
    Best-effort, single structured-output LLM call. Truncates the
    FULL facts from _compute_impact_facts() down to
    MAX_PROMPT_FILES/MAX_PROMPT_NODES here — this is the ONLY place
    in the file truncation happens; `facts` itself is never mutated.
    "id" is stripped from direct_callers/entry_points for the prompt,
    since the LLM has no use for internal node identifiers. Prompt
    JSON uses compact separators to reduce token usage — this only
    removes whitespace, the LLM-visible content is unchanged.

    Returns None on ANY failure — missing provider, network error,
    malformed JSON, or a response that doesn't validate against
    ImpactAIResult — and the caller falls back to the graph-only
    response. Mirrors generate_architecture_summary()'s contract
    exactly.
    """
    prompt_facts = {
        **facts,
        "affected_files": facts["affected_files"][:MAX_PROMPT_FILES],
        "direct_callers": [
            {"file_path": c["file_path"], "function_name": c["function_name"]}
            for c in facts["direct_callers"][:MAX_PROMPT_NODES]
        ],
        "entry_points": [
            {"file_path": e["file_path"], "function_name": e["function_name"]}
            for e in facts["entry_points"][:MAX_PROMPT_NODES]
        ],
    }

    payload = {"query_node": query_node, **prompt_facts, "graph_stats": graph_stats}
    prompt = (
        "Here are the deterministically computed impact facts for a "
        "function that may be changed:\n\n"
        f"{json.dumps(payload, separators=(',', ':'))}\n\n"
        "Write the impact assessment described in your instructions, "
        "based only on these facts."
    )

    try:
        raw = await generate_text(
            prompt=prompt,
            system=_IMPACT_SYSTEM_PROMPT,
            temperature=0.2,
        )
        cleaned = (
            raw.strip()
            .removeprefix("```json")
            .removeprefix("```")
            .removesuffix("```")
            .strip()
        )
        return ImpactAIResult(**json.loads(cleaned))

    except (LLMServiceError, json.JSONDecodeError, ValidationError, KeyError, TypeError) as exc:
        logger.warning(
            "Impact AI reasoning failed for node %s, falling back to "
            "graph-only results: %s",
            query_node, exc,
        )
        return None