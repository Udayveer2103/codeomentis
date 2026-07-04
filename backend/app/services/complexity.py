"""
Complexity scoring — computes the four sub-scores that compose the tech debt
heatmap, then rolls them into a single composite score (0–100).

Scoring signals:
  cc_score        Cyclomatic complexity (radon, Python only; heuristic for JS/TS)
  coupling_score  Import graph in-degree (how many files depend on this file)
  todo_density    (TODO + FIXME count) / line_count
  fn_length_score Average function length normalised against a threshold

Composite formula (weights chosen to make ~20% of files score > 66 in a
typical medium-sized repo):
  composite = 0.35 * cc + 0.25 * coupling + 0.20 * todo + 0.20 * fn_len
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import networkx as nx

# radon is Python-only — guard so the module still imports on systems
# where radon isn't installed yet (though it should be).
try:
    from radon.complexity import cc_visit, ComplexityVisitor
    from radon.metrics import h_visit
    RADON_AVAILABLE = True
except ImportError:
    RADON_AVAILABLE = False

from app.services.ast_walker import FunctionInfo
from app.services.github import RepoFile

logger = logging.getLogger(__name__)

# Thresholds — functions longer than this get max length score
MAX_FUNCTION_LINES = 80
# Files with more than this many callers in the import graph get max coupling
MAX_COUPLING_CALLERS = 20

TODO_PATTERN = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b", re.IGNORECASE)


@dataclass
class FileScore:
    file_path: str
    language: str
    cc_score: float         # 0–100
    coupling_score: float   # 0–100
    todo_density: float     # 0–100
    fn_length_score: float  # 0–100
    composite_score: float  # 0–100 (weighted average)
    severity: str           # low | medium | high
    line_count: int
    function_count: int
    todo_count: int


def score_files(
    files: list[RepoFile],
    functions: list[FunctionInfo],
    import_graph: nx.DiGraph,
) -> list[FileScore]:
    """
    Compute FileScore for every file in the repository.

    Args:
        files:        Raw file objects (content + metadata)
        functions:    All extracted FunctionInfo objects
        import_graph: File-level import graph from graph_builder

    Returns:
        One FileScore per file.
    """
    # Group functions by file for efficient lookup
    funcs_by_file: dict[str, list[FunctionInfo]] = {}
    for fn in functions:
        funcs_by_file.setdefault(fn.file_path, []).append(fn)

    # Compute max in-degree for normalisation
    if import_graph.number_of_nodes() > 0:
        max_in_degree = max(
            (d for _, d in import_graph.in_degree()),
            default=1,
        )
    else:
        max_in_degree = 1

    scores: list[FileScore] = []
    for repo_file in files:
        score = _score_file(
            repo_file,
            funcs_by_file.get(repo_file.path, []),
            import_graph,
            max_in_degree,
        )
        scores.append(score)

    return scores


def _score_file(
    repo_file: RepoFile,
    functions: list[FunctionInfo],
    import_graph: nx.DiGraph,
    max_in_degree: int,
) -> FileScore:
    lines = repo_file.content.splitlines()
    line_count = len(lines)
    if line_count == 0:
        line_count = 1  # avoid division by zero

    # 1. Cyclomatic complexity score
    cc_score = _compute_cc_score(repo_file.content, repo_file.language)

    # 2. Coupling score (import graph in-degree)
    in_degree = import_graph.in_degree(repo_file.path) if repo_file.path in import_graph else 0
    coupling_score = min((in_degree / max(max_in_degree, 1)) * 100, 100)

    # 3. TODO density
    todo_count = len(TODO_PATTERN.findall(repo_file.content))
    todo_density = min((todo_count / line_count) * 1000, 100)  # 10 TODOs/100 lines → 100

    # 4. Function length score
    fn_length_score = _compute_fn_length_score(functions)

    # Weighted composite
    composite = (
        0.35 * cc_score
        + 0.25 * coupling_score
        + 0.20 * todo_density
        + 0.20 * fn_length_score
    )
    composite = min(round(composite, 1), 100)

    severity = _severity(composite)

    return FileScore(
        file_path=repo_file.path,
        language=repo_file.language,
        cc_score=round(cc_score, 1),
        coupling_score=round(coupling_score, 1),
        todo_density=round(todo_density, 1),
        fn_length_score=round(fn_length_score, 1),
        composite_score=composite,
        severity=severity,
        line_count=line_count,
        function_count=len(functions),
        todo_count=todo_count,
    )


def _compute_cc_score(content: str, language: str) -> float:
    """
    Cyclomatic complexity score normalised to 0–100.

    For Python: use radon's cc_visit.
    For JS/TS: heuristic — count branch keywords (if/else/for/while/&&/||/?:).
    """
    if language == "python" and RADON_AVAILABLE:
        try:
            blocks = cc_visit(content)
            if not blocks:
                return 0.0
            avg_cc = sum(b.complexity for b in blocks) / len(blocks)
            # radon complexity 1 = simple, 10+ = complex. Normalise: 10 → 100.
            return min((avg_cc / 10) * 100, 100)
        except Exception:
            pass  # fall through to heuristic

    # JS/TS heuristic — count decision points
    branch_pattern = re.compile(
        r"\b(if|else|for|while|case|catch|&&|\|\||\?)\b"
    )
    matches = branch_pattern.findall(content)
    lines = content.count("\n") + 1
    density = len(matches) / max(lines, 1)
    # ~0.1 branches/line is moderate complexity
    return min((density / 0.2) * 100, 100)


def _compute_fn_length_score(functions: list[FunctionInfo]) -> float:
    """
    Average function length score normalised to 0–100.

    Functions > MAX_FUNCTION_LINES lines get a penalty score.
    """
    if not functions:
        return 0.0
    avg_length = sum(
        fn.end_line - fn.start_line for fn in functions
    ) / len(functions)
    return min((avg_length / MAX_FUNCTION_LINES) * 100, 100)


def _severity(composite: float) -> str:
    if composite >= 66:
        return "high"
    elif composite >= 33:
        return "medium"
    return "low"
