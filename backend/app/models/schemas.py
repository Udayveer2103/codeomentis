from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# ── Repo ──────────────────────────────────────────────────────────────────────

class RepoCreate(BaseModel):
    github_url: str
    user_id: str


class RepoResponse(BaseModel):
    id: str
    user_id: str
    github_url: str
    owner: str
    name: str
    default_branch: str
    language_stats: dict
    status: str
    error_message: Optional[str]
    file_count: int
    architecture_pattern: Optional[str]
    architecture_summary: Optional[str]
    created_at: datetime
    updated_at: datetime


# ── File scores ───────────────────────────────────────────────────────────────

class FileScoreResponse(BaseModel):
    id: str
    repo_id: str
    file_path: str
    language: Optional[str]
    cc_score: float
    coupling_score: float
    todo_density: float
    fn_length_score: float
    composite_score: float
    severity: str
    line_count: int
    function_count: int
    todo_count: int


# ── Impact ────────────────────────────────────────────────────────────────────

class ImpactNode(BaseModel):
    id: str
    file_path: str
    function_name: str
    depth: int


class ImpactLink(BaseModel):
    source: str
    target: str


class ImpactResponse(BaseModel):
    nodes: list[ImpactNode]
    links: list[ImpactLink]


# ── Walkthrough ───────────────────────────────────────────────────────────────

class WalkthroughStep(BaseModel):
    order: int
    file_path: str
    description: str
    why: str
    key_functions: list[str]


class WalkthroughResponse(BaseModel):
    steps: list[WalkthroughStep]
    repo_id: str


# ── Chat ──────────────────────────────────────────────────────────────────────

class ChatMessageIn(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    repo_id: str
    message: str
    history: list[ChatMessageIn] = []
