"""
AST Walker — extracts function definitions and call sites using tree-sitter.

IMPORTANT: Pinned to tree-sitter==0.21.3. The Language() constructor
signature changed in 0.22+. Do not upgrade.

For each file, produces a list of FunctionInfo objects containing:
- Qualified name (file_path::function_name)
- Start/end lines
- List of function names called in the body
- Estimated token count for chunking
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

# tree-sitter 0.21 API
from tree_sitter import Language, Parser
import tree_sitter_python as tspython
import tree_sitter_javascript as tsjavascript
import tree_sitter_typescript as tstypescript

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Language setup (tree-sitter 0.21 style)
# ---------------------------------------------------------------------------

PY_LANGUAGE  = Language(tspython.language(), "python")
JS_LANGUAGE  = Language(tsjavascript.language(), "javascript")
TS_LANGUAGE  = Language(tstypescript.language_typescript(), "typescript")
TSX_LANGUAGE = Language(tstypescript.language_tsx(), "tsx")

_LANG_MAP: dict[str, Language] = {
    "python":     PY_LANGUAGE,
    "javascript": JS_LANGUAGE,
    "typescript": TS_LANGUAGE,
}

# ---------------------------------------------------------------------------
# Query strings — tree-sitter S-expression syntax
# ---------------------------------------------------------------------------

# Python: function_definition and async_function_definition
PY_FUNC_QUERY = PY_LANGUAGE.query("""
  (function_definition name: (identifier) @func_name) @func_def
  (decorated_definition
    definition: (function_definition name: (identifier) @func_name)) @func_def
""")

PY_CALL_QUERY = PY_LANGUAGE.query("""
  (call function: [
    (identifier) @callee
    (attribute attribute: (identifier) @callee)
  ])
""")

JS_FUNC_QUERY = JS_LANGUAGE.query("""
  (function_declaration name: (identifier) @func_name) @func_def
  (method_definition name: (property_identifier) @func_name) @func_def
  (variable_declarator
    name: (identifier) @func_name
    value: [(arrow_function) (function_expression)]) @func_def
""")

JS_CALL_QUERY = JS_LANGUAGE.query("""
  (call_expression function: [
    (identifier) @callee
    (member_expression property: (property_identifier) @callee)
  ])
""")

TS_FUNC_QUERY = TS_LANGUAGE.query("""
  (function_declaration name: (identifier) @func_name) @func_def
  (method_definition name: (property_identifier) @func_name) @func_def
  (variable_declarator
    name: (identifier) @func_name
    value: [(arrow_function) (function_expression)]) @func_def
""")

TS_CALL_QUERY = TS_LANGUAGE.query("""
  (call_expression function: [
    (identifier) @callee
    (member_expression property: (property_identifier) @callee)
  ])
""")


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class FunctionInfo:
    """A single function/method extracted from a source file."""
    qualified_name: str          # "src/auth.py::verify_token"
    function_name: str           # "verify_token"
    file_path: str               # "src/auth.py"
    language: str
    start_line: int              # 1-indexed
    end_line: int
    content: str                 # raw source of this function
    callees: list[str] = field(default_factory=list)  # names of called functions
    chunk_type: str = "function"


@dataclass
class ClassInfo:
    """A class extracted for chunking (not used in call graph directly)."""
    qualified_name: str
    class_name: str
    file_path: str
    language: str
    start_line: int
    end_line: int
    content: str
    chunk_type: str = "class"


# ---------------------------------------------------------------------------
# Main walker
# ---------------------------------------------------------------------------

class ASTWalker:
    """
    Extract functions (and optionally classes) from source files.

    Usage:
        walker = ASTWalker()
        functions = walker.extract_functions("src/auth.py", source_code, "python")
    """

    def __init__(self) -> None:
        self._parsers: dict[str, Parser] = {}

    def _get_parser(self, language: str) -> Parser:
        if language not in self._parsers:
            lang_obj = _LANG_MAP.get(language)
            if lang_obj is None:
                raise ValueError(f"Unsupported language: {language!r}")
            p = Parser()
            p.set_language(lang_obj)
            self._parsers[language] = p
        return self._parsers[language]

    def extract_functions(
        self,
        file_path: str,
        source: str,
        language: str,
    ) -> list[FunctionInfo]:
        """
        Parse source and return one FunctionInfo per function definition.

        Gracefully returns [] on parse errors — a bad file should never
        crash the whole ingestion pipeline.
        """
        try:
            return self._extract(file_path, source, language)
        except Exception as exc:
            logger.warning("AST extraction failed for %s: %s", file_path, exc)
            return []

    def _extract(
        self,
        file_path: str,
        source: str,
        language: str,
    ) -> list[FunctionInfo]:
        parser = self._get_parser(language)
        source_bytes = source.encode("utf-8")
        tree = parser.parse(source_bytes)

        func_query, call_query = _get_queries(language)

        # Capture all function definitions
        func_matches = func_query.matches(tree.root_node)

        results: list[FunctionInfo] = []
        for _, capture_dict in func_matches:
            func_def_nodes = capture_dict.get("func_def", [])
            func_name_nodes = capture_dict.get("func_name", [])

            # matches() returns lists or single nodes depending on version
            if not isinstance(func_def_nodes, list):
                func_def_nodes = [func_def_nodes]
            if not isinstance(func_name_nodes, list):
                func_name_nodes = [func_name_nodes]

            if not func_def_nodes or not func_name_nodes:
                continue

            func_node = func_def_nodes[0]
            name_node = func_name_nodes[0]

            func_name = name_node.text.decode("utf-8")
            start_line = func_node.start_point[0] + 1
            end_line   = func_node.end_point[0] + 1

            func_content = source_bytes[
                func_node.start_byte : func_node.end_byte
            ].decode("utf-8", errors="replace")

            # Find all call sites within this function body
            callees = self._find_callees(func_node, call_query)

            results.append(FunctionInfo(
                qualified_name=f"{file_path}::{func_name}",
                function_name=func_name,
                file_path=file_path,
                language=language,
                start_line=start_line,
                end_line=end_line,
                content=func_content,
                callees=callees,
            ))

        return results

    def _find_callees(self, func_node, call_query) -> list[str]:
        """Extract unique callee names from call sites within a function."""
        call_matches = call_query.matches(func_node)
        callees: set[str] = set()
        for _, capture_dict in call_matches:
            callee_nodes = capture_dict.get("callee", [])
            if not isinstance(callee_nodes, list):
                callee_nodes = [callee_nodes]
            for node in callee_nodes:
                name = node.text.decode("utf-8")
                if name and len(name) < 100:  # sanity cap
                    callees.add(name)
        return sorted(callees)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_queries(language: str):
    """Return (func_query, call_query) tuple for the given language."""
    if language == "python":
        return PY_FUNC_QUERY, PY_CALL_QUERY
    elif language == "javascript":
        return JS_FUNC_QUERY, JS_CALL_QUERY
    elif language in ("typescript", "tsx"):
        return TS_FUNC_QUERY, TS_CALL_QUERY
    else:
        raise ValueError(f"No queries for language: {language!r}")