"""
Developer-only verification tool for the Walkthrough redesign.

Prints the deterministic role classification + feature grouping output as
a tree, so role/grouping behavior can be eyeballed against a real repo's
call graph before the frontend consumes it. Not imported by any router or
production code path — safe to delete once the redesign is validated.

Usage (from the backend project root, with the venv active):
    python -m app.services.walkthrough_debug <repo_id>

Or from Python directly:
    from app.services.walkthrough_debug import print_walkthrough_tree
    print_walkthrough_tree("38bc4882-a18e-4c8a-bf92-7e056c702d55")
"""

from __future__ import annotations

import sys

from app.services.walkthrough import _compute_reading_order, _load_call_graph


def print_walkthrough_tree(repo_id: str) -> None:
    """Loads the real call graph for repo_id and prints the resulting
    group -> steps tree, with each step's assigned role. Pure read-only
    inspection — does not call the LLM, does not read/write
    walkthrough_steps, does not affect caching."""
    graph = _load_call_graph(repo_id)
    steps = _compute_reading_order(graph)

    if not steps:
        print(f"(no walkthrough steps computed for repo {repo_id} — empty or disconnected graph)")
        return

    current_group = None
    for step in steps:
        if step.group_label != current_group:
            current_group = step.group_label
            print(current_group)
        label = step.function_name or step.file_path.rsplit("/", 1)[-1]
        print(f"├── {label} ({step.role})  [{step.file_path}]")

    print()
    print(f"Total: {len(steps)} steps across {len({s.group_label for s in steps})} groups")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m app.services.walkthrough_debug <repo_id>")
        sys.exit(1)
    print_walkthrough_tree(sys.argv[1])