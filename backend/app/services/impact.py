"""
impact.py  —  RepoMind Week 3 service layer

Loads call_graph.json from Supabase Storage, rebuilds it
as a NetworkX DiGraph, reverses it, and runs BFS from the
queried node to find every caller in the blast radius.
"""

import json
from collections import deque
from typing import Any

import networkx as nx

# ── Supabase storage path ──────────────────────────────────────────────────────
GRAPH_BUCKET = "graphs"


async def run_impact_analysis(
    supabase,
    repo_id: str,
    query_node: str,
    max_depth: int = 5,
) -> dict[str, Any]:
    """
    1. Fetch call_graph.json from Supabase Storage
    2. Build DiGraph with networkx
    3. Reverse graph  (edges now point FROM caller TO callee)
    4. BFS from query_node up to max_depth
    5. Return node + link lists for D3
    """

    # ── 1. Load graph JSON ────────────────────────────────────────────────────
    graph_json = _load_graph(supabase, repo_id)
    if not graph_json:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Call graph not found — has this repo been ingested?")

    # ── 2. Build NetworkX graph ───────────────────────────────────────────────
    G: nx.DiGraph = nx.node_link_graph(graph_json, directed=True, multigraph=False)

    # ── 3. Validate query node ────────────────────────────────────────────────
    if query_node not in G.nodes:
        # Try case-insensitive fuzzy match — return suggestions
        suggestions = _fuzzy_match(G, query_node, limit=10)
        from fastapi import HTTPException
        raise HTTPException(
            status_code=404,
            detail={
                "message": f"Function '{query_node}' not found in call graph",
                "suggestions": suggestions,
            },
        )

    # ── 4. Reverse + BFS ─────────────────────────────────────────────────────
    R: nx.DiGraph = G.reverse(copy=True)   # reversed: edge = caller → callee
    bfs_nodes, bfs_links = _bfs(R, query_node, max_depth)

    # ── 5. Shape response for D3 ─────────────────────────────────────────────
    nodes = []
    for node_id, depth in bfs_nodes.items():
        file_path, _, fn_name = node_id.rpartition("::")
        nodes.append({
            "id": node_id,
            "file_path": file_path or node_id,
            "function_name": fn_name or node_id,
            "depth": depth,
        })

    # Sort so root is first
    nodes.sort(key=lambda n: n["depth"])

    links = [
        {"source": s, "target": t, "depth": d}
        for s, t, d in bfs_links
    ]

    return {
        "query_node": query_node,
        "nodes": nodes,
        "links": links,
        "total_impacted": len(nodes) - 1,   # exclude root itself
        "graph_stats": {
            "total_nodes": G.number_of_nodes(),
            "total_edges": G.number_of_edges(),
        },
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _load_graph(supabase, repo_id: str) -> dict | None:
    """Download call_graph.json from Supabase Storage bucket."""
    try:
        path = f"{repo_id}/call_graph.json"
        res = supabase.storage.from_(GRAPH_BUCKET).download(path)
        if isinstance(res, (bytes, bytearray)):
            return json.loads(res.decode("utf-8"))
        return None
    except Exception as e:
        print(f"[impact] Failed to load graph for {repo_id}: {e}")
        return None


def _bfs(
    G: nx.DiGraph,
    start: str,
    max_depth: int,
) -> tuple[dict[str, int], list[tuple[str, str, int]]]:
    """
    BFS on the REVERSED graph.
    Returns:
      visited  — {node_id: depth}
      edges    — [(source, target, depth)]  where depth = depth of source node
    """
    visited: dict[str, int] = {start: 0}
    edges: list[tuple[str, str, int]] = []
    queue: deque[tuple[str, int]] = deque([(start, 0)])

    while queue:
        node, depth = queue.popleft()
        if depth >= max_depth:
            continue
        for neighbor in G.successors(node):   # reversed graph: successor = original caller
            if neighbor not in visited:
                visited[neighbor] = depth + 1
                edges.append((neighbor, node, depth + 1))
                queue.append((neighbor, depth + 1))

    return visited, edges


def _fuzzy_match(G: nx.DiGraph, query: str, limit: int = 10) -> list[str]:
    """Return up to `limit` node IDs that contain the query string."""
    q = query.lower()
    return [n for n in G.nodes if q in n.lower()][:limit]