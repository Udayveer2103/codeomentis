"""
Graph builder — constructs call graph and import graph using NetworkX.

Produces two graphs:
1. call_graph   (DiGraph) — directed edges from callee → caller (reversed for
   easy BFS "who calls X" queries in the Impact Analyzer)
2. import_graph (DiGraph) — directed edges showing file import relationships

Both graphs are serialised to JSON via nx.node_link_data() for storage in
Supabase Storage.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import networkx as nx

from app.services.ast_walker import FunctionInfo

logger = logging.getLogger(__name__)


@dataclass
class GraphBundle:
    """Container for the two graphs and their node metadata."""
    call_graph: nx.DiGraph
    import_graph: nx.DiGraph
    # Keyed by qualified_name — used for node metadata in the API response
    node_meta: dict[str, dict]


def build_call_graph(functions: list[FunctionInfo]) -> GraphBundle:
    """
    Build call graph and import graph from extracted function data.

    Call graph edges: caller → callee
    (The Impact Analyzer reverses this to find callers of a given function.)

    Node attributes stored on each graph node:
      - file_path
      - function_name
      - start_line / end_line
      - language

    Args:
        functions: All FunctionInfo objects from all files in the repo.

    Returns:
        GraphBundle with call_graph, import_graph, and node_meta dict.
    """
    call_graph = nx.DiGraph()
    import_graph = nx.DiGraph()
    node_meta: dict[str, dict] = {}

    # Index all known functions by name (unqualified) for callee resolution
    name_to_qualified: dict[str, list[str]] = {}
    for fn in functions:
        call_graph.add_node(
            fn.qualified_name,
            file_path=fn.file_path,
            function_name=fn.function_name,
            start_line=fn.start_line,
            end_line=fn.end_line,
            language=fn.language,
        )
        node_meta[fn.qualified_name] = {
            "file_path": fn.file_path,
            "function_name": fn.function_name,
            "start_line": fn.start_line,
            "end_line": fn.end_line,
            "language": fn.language,
        }
        name_to_qualified.setdefault(fn.function_name, []).append(fn.qualified_name)

    # Build edges: caller → callee (resolve callee by unqualified name)
    for fn in functions:
        for callee_name in fn.callees:
            callee_qualified_list = name_to_qualified.get(callee_name, [])
            for callee_qualified in callee_qualified_list:
                if callee_qualified != fn.qualified_name:  # no self-loops
                    call_graph.add_edge(fn.qualified_name, callee_qualified)

    # Build import graph (file-level, not function-level)
    _build_import_graph(import_graph, functions)

    # Compute degree metrics and store on nodes
    in_degrees  = dict(call_graph.in_degree())
    out_degrees = dict(call_graph.out_degree())
    for node in call_graph.nodes:
        call_graph.nodes[node]["in_degree"]  = in_degrees.get(node, 0)
        call_graph.nodes[node]["out_degree"] = out_degrees.get(node, 0)
        if node in node_meta:
            node_meta[node]["in_degree"]  = in_degrees.get(node, 0)
            node_meta[node]["out_degree"] = out_degrees.get(node, 0)

    logger.info(
        "Built call graph: %d nodes, %d edges",
        call_graph.number_of_nodes(),
        call_graph.number_of_edges(),
    )

    return GraphBundle(
        call_graph=call_graph,
        import_graph=import_graph,
        node_meta=node_meta,
    )


def serialise_graph(graph: nx.DiGraph) -> str:
    """Serialise a NetworkX graph to a JSON string."""
    data = nx.node_link_data(graph)
    return json.dumps(data)


def deserialise_graph(json_str: str) -> nx.DiGraph:
    """Rebuild a NetworkX DiGraph from a JSON string produced by serialise_graph."""
    data = json.loads(json_str)
    return nx.node_link_graph(data, directed=True, multigraph=False)


# ---------------------------------------------------------------------------
# Import graph helper
# ---------------------------------------------------------------------------

def _build_import_graph(
    import_graph: nx.DiGraph,
    functions: list[FunctionInfo],
) -> None:
    """
    Build a file-level import graph.

    Currently uses a heuristic: if file A defines a function that is called
    by file B, we infer B imports A. This avoids actually parsing import
    statements (which varies by language) while still capturing the coupling
    structure that matters for the heatmap.

    A full import-statement parser would be more accurate but requires
    separate queries per language and relative-path resolution. Good enough
    for MVP.
    """
    # Group functions by file
    file_to_functions: dict[str, list[FunctionInfo]] = {}
    for fn in functions:
        file_to_functions.setdefault(fn.file_path, []).append(fn)

    # All files are nodes
    for file_path in file_to_functions:
        import_graph.add_node(file_path)

    # For each function call that crosses file boundaries, add an import edge
    name_to_file: dict[str, str] = {
        fn.function_name: fn.file_path for fn in functions
    }
    for fn in functions:
        for callee_name in fn.callees:
            callee_file = name_to_file.get(callee_name)
            if callee_file and callee_file != fn.file_path:
                import_graph.add_edge(fn.file_path, callee_file)