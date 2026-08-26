from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import List, Optional

from github import Github
from github.GithubException import GithubException, RateLimitExceededException

from app.config import settings


SUPPORTED_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
}

# Exact filenames recognized as architecture-relevant config.
# Lockfiles are intentionally excluded — not needed for detection or
# explanation, and some (yarn.lock, package-lock.json) can be very large.
CONFIG_FILENAMES = {
    "package.json",
    "tsconfig.json",
    "next.config.js",
    "next.config.ts",
    "next.config.mjs",
    "vite.config.ts",
    "vite.config.js",
    "tailwind.config.ts",
    "tailwind.config.js",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "railway.json",
    "vercel.json",
    "render.yaml",
    "fly.toml",
    "requirements.txt",
    "pyproject.toml",
    "Pipfile",
    "prisma.schema",
    "schema.prisma",
    "drizzle.config.ts",
    "drizzle.config.js",
}

# Path prefixes checked separately since these aren't fixed filenames
# (e.g. .github/workflows/deploy.yml, .github/workflows/ci.yml).
CONFIG_DIR_PREFIXES = (".github/workflows/",)

# Config files are expected to be small (manifests, not data). Skip
# content on anything larger than this to avoid pathological repos
# bloating storage — path/language are still recorded either way.
MAX_CONFIG_FILE_BYTES = 50_000


@dataclass
class RepoFile:
    path: str
    content: str
    language: str = ""


@dataclass
class RepoMeta:
    owner: str
    name: str
    default_branch: str
    language_stats: dict
    files: List[RepoFile]
    config_files: List[RepoFile] = field(default_factory=list)


class GitHubService:
    def __init__(self):
        # timeout: bound every individual HTTP call so nothing waits
        # forever on a slow/hung connection.
        # retry=0: disable PyGithub's built-in automatic retry/backoff,
        # so a rate-limit or API failure raises immediately instead of
        # silently sleeping/retrying, and propagates up through
        # asyncio.to_thread into run_ingestion()'s existing
        # `except Exception -> _mark_error` handling, unchanged.
        self.client = Github(
            settings.github_token,
            timeout=20,
            retry=0,
        )

    def fetch_repo(self, github_url: str) -> RepoMeta:
        """
        Fetch repository contents from GitHub.

        Supports:
        - https://github.com/owner/repo
        - https://github.com/owner/repo/
        - https://github.com/owner/repo.git

        Uses the Git Trees API (one recursive call) to discover the full
        file tree in a single request, then applies
        settings.max_files_per_repo / settings.max_file_size_kb against
        that tree's metadata (path + size, both already included in the
        tree response) BEFORE fetching any file content — so content is
        only ever fetched for files that will actually be analyzed, and
        the total number of API calls stays bounded regardless of how
        large the source repository is. This replaces the previous
        recursive `get_contents()` walk, which made one API call per
        directory and had no size/count limit at all.

        Returns source files (matched by SUPPORTED_EXTENSIONS) in `files`,
        and architecture-relevant config files (matched by CONFIG_FILENAMES
        or CONFIG_DIR_PREFIXES) separately in `config_files`. A file is
        never counted in both lists.
        """

        github_url = github_url.strip().rstrip("/")

        if github_url.endswith(".git"):
            github_url = github_url[:-4]

        repo_name = github_url.replace(
            "https://github.com/",
            ""
        )

        try:
            repo = self.client.get_repo(repo_name)

            git_tree = repo.get_git_tree(
                repo.default_branch,
                recursive=True,
            )

            language_stats = repo.get_languages()

        except RateLimitExceededException as exc:
            raise RuntimeError(
                "GitHub API rate limit exceeded while fetching "
                f"{repo_name}. Try again later, or configure a "
                "GITHUB_TOKEN with a higher rate limit."
            ) from exc

        except GithubException as exc:
            raise RuntimeError(
                f"GitHub API error while fetching {repo_name}: "
                f"{exc.status} {exc.data.get('message', '') if isinstance(exc.data, dict) else ''}".strip()
            ) from exc

        # This project's installed PyGithub version does not expose a
        # working GitTree.truncated property (confirmed by the runtime
        # error "'GitTree' object has no attribute 'truncated'").
        # raw_data is a plain property on the base GithubObject class
        # (just returns the underlying response dict, no version-added
        # convenience property involved), so this reads GitHub's raw
        # JSON directly instead of depending on that attribute existing.
        # If truncation genuinely can't be determined this way either,
        # this safely defaults to "not truncated" rather than blocking
        # ingestion on a check we can't perform — the existing
        # max_files_per_repo/max_file_size_kb limits below still bound
        # the ingestion regardless.
        raw_tree_data = getattr(git_tree, "raw_data", None) or {}

        if raw_tree_data.get("truncated"):
            # GitHub's tree API truncates the response for repositories
            # with an extremely large number of entries. Continuing
            # would mean silently analyzing an incomplete/arbitrary
            # subset of the repo with no indication to the user — treat
            # this the same as any other fetch failure rather than
            # letting it pass silently.
            raise RuntimeError(
                f"GitHub returned a truncated file tree for {repo_name} "
                "(too many files/directories to enumerate in one "
                "request). This repository cannot be safely ingested "
                "with the current fetch strategy."
            )

        max_files = settings.max_files_per_repo
        max_file_bytes = settings.max_file_size_kb * 1024

        source_candidates: List[tuple[str, str, str]] = []  # (path, sha, language)
        config_candidates: List[tuple[str, str]] = []  # (path, sha)
        config_stubs: List[RepoFile] = []  # oversized config files — path only, no content

        for element in git_tree.tree:

            if element.type != "blob":
                continue

            path = element.path
            size: Optional[int] = element.size

            language = self._detect_language(path)

            if language:
                if len(source_candidates) >= max_files:
                    # Already have enough qualifying source files —
                    # skip remaining ones rather than fetching content
                    # we're just going to discard.
                    continue

                if size is not None and size > max_file_bytes:
                    continue

                source_candidates.append((path, element.sha, language))
                continue

            if self._is_config_file(path):
                if size is not None and size > MAX_CONFIG_FILE_BYTES:
                    config_stubs.append(
                        RepoFile(path=path, content="", language="config")
                    )
                    continue

                config_candidates.append((path, element.sha))

        files: List[RepoFile] = []

        for path, sha, language in source_candidates:
            content = self._fetch_blob_text(repo, sha)

            if content is None:
                continue

            files.append(RepoFile(path=path, content=content, language=language))

        config_files: List[RepoFile] = list(config_stubs)

        for path, sha in config_candidates:
            content = self._fetch_blob_text(repo, sha)

            if content is None:
                continue

            config_files.append(RepoFile(path=path, content=content, language="config"))

        return RepoMeta(
            owner=repo.owner.login,
            name=repo.name,
            default_branch=repo.default_branch,
            language_stats=language_stats,
            files=files,
            config_files=config_files,
        )

    def _fetch_blob_text(self, repo, sha: str) -> Optional[str]:
        try:
            blob = repo.get_git_blob(sha)
            raw = base64.b64decode(blob.content)
            return raw.decode("utf-8")
        except RateLimitExceededException:
            raise
        except Exception:
            # Same behavior as before: a single undecodable/binary/
            # inaccessible file is skipped, not fatal to the whole
            # ingestion.
            return None

    def _detect_language(self, path: str) -> str:
        for ext, language in SUPPORTED_EXTENSIONS.items():
            if path.endswith(ext):
                return language
        return ""

    def _is_config_file(self, path: str) -> bool:
        filename = path.rsplit("/", 1)[-1]

        if filename in CONFIG_FILENAMES:
            return True

        return any(path.startswith(prefix) for prefix in CONFIG_DIR_PREFIXES)