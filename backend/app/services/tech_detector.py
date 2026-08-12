"""
TechDetector — single deterministic source of truth for architecture
detection.

Combines:
- file-path heuristics for architecture pattern (mvc/hexagonal/flat) —
  moved here unchanged from ingestion.py's former _detect_architecture()
- config file parsing (package.json, pyproject.toml, requirements.txt)
  to infer frameworks, database, ORM, auth, styling, AI providers,
  deployment target, and package manager

Produces the tech_stack dict written to repos.tech_stack. Never
guesses — a category is omitted when nothing in the repo's own
files supports a conclusion. No LLM involved; this output is what
the AI summary explains later, not what it discovers.
"""

from __future__ import annotations

import json
import logging
import re
import tomllib
from typing import Optional

from app.services.github import RepoFile

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Architecture pattern detection (unchanged from ingestion._detect_architecture)
# ---------------------------------------------------------------------------

def detect_architecture_pattern(files: list[RepoFile]) -> str:

    paths = " ".join(
        f.path for f in files
    ).lower()

    has_models = "model" in paths or "models/" in paths
    has_views = "view" in paths or "views/" in paths or "template" in paths
    has_routes = "route" in paths or "router" in paths or "controller" in paths
    has_domain = "domain/" in paths
    has_use_cases = "usecase" in paths or "use_case" in paths
    has_ports = "port" in paths or "adapter" in paths

    if has_domain and (has_use_cases or has_ports):
        return "hexagonal"

    elif has_models and has_views and has_routes:
        return "mvc"

    elif not has_models and not has_views:
        return "flat"

    return "unknown"


# ---------------------------------------------------------------------------
# Known dependency -> technology mappings
# ---------------------------------------------------------------------------

FRONTEND_FRAMEWORKS = {
    "next": "Next.js",
    "react": "React",
    "vue": "Vue",
    "svelte": "Svelte",
    "@angular/core": "Angular",
}

BACKEND_FRAMEWORKS_JS = {
    "express": "Express",
    "fastify": "Fastify",
    "@nestjs/core": "NestJS",
}

BACKEND_FRAMEWORKS_PY = {
    "fastapi": "FastAPI",
    "flask": "Flask",
    "django": "Django",
}

DATABASES = {
    "pg": "PostgreSQL",
    "postgres": "PostgreSQL",
    "psycopg2": "PostgreSQL",
    "psycopg2-binary": "PostgreSQL",
    "mongodb": "MongoDB",
    "mongoose": "MongoDB (via Mongoose)",
    "pymongo": "MongoDB",
    "mysql": "MySQL",
    "mysql2": "MySQL",
    "mysqlclient": "MySQL",
    "sqlite3": "SQLite",
    "redis": "Redis",
    "supabase": "Supabase",
}

ORMS = {
    "prisma": "Prisma",
    "drizzle-orm": "Drizzle",
    "sqlalchemy": "SQLAlchemy",
    "typeorm": "TypeORM",
    "mongoose": "Mongoose",
}

AUTH_PROVIDERS = {
    "next-auth": "NextAuth.js",
    "@clerk/nextjs": "Clerk",
    "@supabase/auth-helpers-nextjs": "Supabase Auth",
    "passport": "Passport.js",
    "firebase-admin": "Firebase Auth",
    "python-jose": "JWT (python-jose)",
    "pyjwt": "JWT (PyJWT)",
}

STYLING = {
    "tailwindcss": "Tailwind CSS",
    "styled-components": "styled-components",
    "@emotion/react": "Emotion",
    "sass": "Sass",
}

AI_PROVIDERS = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "langchain": "LangChain",
    "@langchain/core": "LangChain",
    "groq": "Groq",
    "ollama": "Ollama",
}

DEPLOYMENT_FILES = {
    "Dockerfile": "Docker",
    "docker-compose.yml": "Docker Compose",
    "docker-compose.yaml": "Docker Compose",
    "railway.json": "Railway",
    "vercel.json": "Vercel",
    "render.yaml": "Render",
    "fly.toml": "Fly.io",
}


# ---------------------------------------------------------------------------
# Config file parsing — each parser is best-effort and returns None on
# anything it can't confidently read, rather than raising.
# ---------------------------------------------------------------------------

def _parse_package_json(content: str) -> Optional[dict]:
    try:
        data = json.loads(content)
    except Exception as exc:
        logger.debug("Failed to parse package.json: %s", exc)
        return None

    return {
        "dependencies": list(data.get("dependencies", {}).keys()),
        "dev_dependencies": list(data.get("devDependencies", {}).keys()),
    }


def _parse_requirements_txt(content: str) -> Optional[dict]:
    deps = []

    for line in content.splitlines():
        line = line.strip()

        if not line or line.startswith("#") or line.startswith("-"):
            continue

        name = re.split(r"[=<>!~\[]", line, maxsplit=1)[0].strip()

        if name:
            deps.append(name.lower())

    return {"dependencies": deps} if deps else None


def _parse_pyproject_toml(content: str) -> Optional[dict]:
    try:
        data = tomllib.loads(content)
    except Exception as exc:
        logger.debug("Failed to parse pyproject.toml: %s", exc)
        return None

    deps = []

    # PEP 621 style: [project] dependencies = ["fastapi>=0.100", ...]
    for dep in data.get("project", {}).get("dependencies", []):
        name = re.split(r"[=<>!~\[\s]", dep, maxsplit=1)[0].strip()
        if name:
            deps.append(name.lower())

    # Poetry style: [tool.poetry.dependencies]
    poetry_deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
    for name in poetry_deps:
        if name.lower() != "python":
            deps.append(name.lower())

    return {"dependencies": deps} if deps else None


_CONFIG_PARSERS = {
    "package.json": _parse_package_json,
    "requirements.txt": _parse_requirements_txt,
    "pyproject.toml": _parse_pyproject_toml,
}


def _extract_dependencies(config_files: list[RepoFile]) -> list[str]:
    """Every dependency name found across all parseable manifests, lowercased."""

    all_deps: set[str] = set()

    for cf in config_files:
        filename = cf.path.rsplit("/", 1)[-1]
        parser = _CONFIG_PARSERS.get(filename)

        if parser is None or not cf.content:
            continue

        parsed = parser(cf.content)

        if not parsed:
            continue

        for dep in parsed.get("dependencies", []):
            all_deps.add(dep.lower())

        for dep in parsed.get("dev_dependencies", []):
            all_deps.add(dep.lower())

    return sorted(all_deps)


def _match(deps: list[str], mapping: dict[str, str]) -> list[str]:
    """Display names for every mapping key present in deps, in mapping order."""

    matched = []

    for key, label in mapping.items():
        if key.lower() in deps and label not in matched:
            matched.append(label)

    return matched


def _detect_deployment(config_files: list[RepoFile]) -> list[str]:
    present = {cf.path.rsplit("/", 1)[-1] for cf in config_files}

    targets = [
        label for filename, label in DEPLOYMENT_FILES.items()
        if filename in present
    ]

    has_workflow = any(
        cf.path.startswith(".github/workflows/") for cf in config_files
    )

    if has_workflow:
        targets.append("GitHub Actions")

    return targets


def _detect_package_manager(config_files: list[RepoFile]) -> Optional[str]:
    paths = {cf.path for cf in config_files}

    if any(p.endswith("package.json") for p in paths):
        return "npm"

    if any(
        p.endswith(("requirements.txt", "pyproject.toml", "Pipfile"))
        for p in paths
    ):
        return "pip"

    return None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def detect_tech_stack(
    files: list[RepoFile],
    config_files: list[RepoFile],
    language_stats: dict,
) -> dict:
    """
    Deterministically infer the repository's tech stack from its
    dependency manifests, config files, and language distribution.

    Called once during ingestion; the result is written to
    repos.tech_stack. Nothing here is persisted per-file — only
    this final aggregated dict.
    """

    deps = _extract_dependencies(config_files)

    return {
        "languages": language_stats,
        "frontend_framework": _match(deps, FRONTEND_FRAMEWORKS) or None,
        "backend_framework": (
            _match(deps, BACKEND_FRAMEWORKS_JS)
            + _match(deps, BACKEND_FRAMEWORKS_PY)
        ) or None,
        "database": _match(deps, DATABASES) or None,
        "orm": _match(deps, ORMS) or None,
        "authentication": _match(deps, AUTH_PROVIDERS) or None,
        "styling": _match(deps, STYLING) or None,
        "ai_providers": _match(deps, AI_PROVIDERS) or None,
        "deployment": _detect_deployment(config_files) or None,
        "package_manager": _detect_package_manager(config_files),
    }