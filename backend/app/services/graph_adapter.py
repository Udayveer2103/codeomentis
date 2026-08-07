"""
Graph adapter — reshapes the existing persisted call graph
(graphs/{repo_id}/call_graph.json in Supabase Storage, produced by
graph_builder.py during ingestion) into React Flow node/edge format
for the Architecture Graph Engine.

Does not modify graph_builder.py and does not change the stored
graph schema — deserialise_graph() is reused exactly as-is.

Two views, both derived from the single persisted call_graph:
- "module": call graph collapsed to file-level nodes (nodes sharing
  a file_path are merged; edges between files are deduplicated).
  import_graph exists in graph_builder's GraphBundle but is never
  persisted to Storage — it's only used transiently for complexity
  scoring in ingestion.py — so it isn't available at request time.
  Module view is therefore derived from call_graph, not a separate
  file.
- "calls": the call graph as-is, function-level.
"""

from __future__ import annotations

import logging

import networkx as nx

from app.db.supabase import get_supabase_client
from app.services.graph_builder import deserialise_graph

logger = logging.getLogger(__name__)

VALID_VIEWS = {"module", "calls"}


class GraphNotFoundError(Exception):
    pass


def get_architecture_graph(repo_id: str, view: str = "module") -> dict:
    """
    Returns React Flow-shaped {"nodes": [...], "edges": [...]} for the
    requested view of the given repo's persisted call graph.
    """

    if view not in VALID_VIEWS:
        raise ValueError(f"Unknown graph view: {view!r}")

    graph = _load_call_graph(repo_id)

    if view == "module":
        return _to_module_view(graph)

    return _to_calls_view(graph)


def _load_call_graph(repo_id: str) -> nx.DiGraph:
    supabase = get_supabase_client()
    storage_path = f"{repo_id}/call_graph.json"

    try:
        raw = supabase.storage.from_("graphs").download(storage_path)
    except Exception as exc:
        raise GraphNotFoundError(
            f"No call graph found for repo {repo_id}"
        ) from exc

    json_str = raw.decode("utf-8") if isinstance(raw, bytes) else raw

    return deserialise_graph(json_str)


def _to_calls_view(graph: nx.DiGraph) -> dict:
    """Function-level — one React Flow node per call graph node."""

    nodes = [
        {
            "id": node_id,
            "type": "function",
            "data": {
                "label": attrs.get("function_name", node_id),
                "file_path": attrs.get("file_path"),
                "language": attrs.get("language"),
                "in_degree": attrs.get("in_degree", 0),
                "out_degree": attrs.get("out_degree", 0),
            },
        }
        for node_id, attrs in graph.nodes(data=True)
    ]

    edges = [
        {
            "id": f"{source}->{target}",
            "source": source,
            "target": target,
        }
        for source, target in graph.edges()
    ]

    return {"nodes": nodes, "edges": edges}


def _to_module_view(graph: nx.DiGraph) -> dict:
    """
    Collapses the function-level call graph to one node per file.
    An edge between two files exists if any function in file A calls
    any function in file B; edges are deduplicated, not weighted —
    weighting can be added later if the graph proves too sparse to
    be useful as-is.
    """

    file_function_counts: dict[str, int] = {}

    for _, attrs in graph.nodes(data=True):
        file_path = attrs.get("file_path")
        if file_path:
            file_function_counts[file_path] = (
                file_function_counts.get(file_path, 0) + 1
            )

    nodes = [
        {
            "id": file_path,
            "type": "module",
            "data": {
                "label": file_path,
                "function_count": count,
            },
        }
        for file_path, count in file_function_counts.items()
    ]

    seen_edges: set[tuple[str, str]] = set()
    edges = []

    for source, target in graph.edges():
        source_file = graph.nodes[source].get("file_path")
        target_file = graph.nodes[target].get("file_path")

        if not source_file or not target_file or source_file == target_file:
            continue

        edge_key = (source_file, target_file)

        if edge_key in seen_edges:
            continue

        seen_edges.add(edge_key)

        edges.append({
            "id": f"{source_file}->{target_file}",
            "source": source_file,
            "target": target_file,
        })

    return {"nodes": nodes, "edges": edges}