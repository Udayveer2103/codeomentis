"""
GitHub service — fetches repository file tree and file contents.

Uses PyGithub with a personal access token for authenticated requests
(5000 req/hour vs 60 unauthenticated). Filters to supported languages only
and respects MAX_FILES_PER_REPO and MAX_FILE_SIZE_KB limits.
"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass, field
from typing import Generator

from github import Github, GithubException, RateLimitExceededException
from github.Repository import Repository

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Supported languages
# ---------------------------------------------------------------------------

SUPPORTED_EXTENSIONS: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
}

# ---------------------------------------------------------------------------
# Paths to skip
# ---------------------------------------------------------------------------

SKIP_PATHS = {
    "node_modules",
    ".git",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "build",
    ".next",
    "venv",
    ".venv",
    "env",
    "vendor",
    "third_party",
    "site-packages",
}

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class RepoFile:
    path: str
    language: str
    content: str
    size_bytes: int


@dataclass
class RepoMetadata:
    owner: str
    name: str
    default_branch: str
    description: str
    language_stats: dict[str, int] = field(default_factory=dict)
    files: list[RepoFile] = field(default_factory=list)


# ---------------------------------------------------------------------------
# GitHub service
# ---------------------------------------------------------------------------


class GitHubService:

    def __init__(self) -> None:

        token = settings.github_token

        self._gh = Github(token) if token else Github()

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def fetch_repo(self, github_url: str) -> RepoMetadata:
        """
        Fetch all parseable files from a GitHub repository.
        """

        owner, name = self._parse_url(github_url)

        logger.info(
            "Fetching repository: %s/%s",
            owner,
            name,
        )

        try:

            repo = self._gh.get_repo(f"{owner}/{name}")

        except RateLimitExceededException:

            raise RuntimeError(
                "GitHub rate limit exceeded. "
                "Add a GITHUB_TOKEN to your .env"
            )

        except GithubException as e:

            if e.status == 404:
                raise ValueError(
                    f"Repository {owner}/{name} not found or is private"
                )

            raise RuntimeError(
                f"GitHub API error: "
                f"{e.data.get('message', str(e))}"
            )

        metadata = RepoMetadata(
            owner=owner,
            name=name,
            default_branch=repo.default_branch,
            description=repo.description or "",
        )

        files = list(self._iter_files(repo))

        metadata.files = files[: settings.max_files_per_repo]

        # Build language stats
        for f in metadata.files:

            metadata.language_stats[f.language] = (
                metadata.language_stats.get(f.language, 0) + 1
            )

        logger.info(
            "Fetched %d files from %s/%s (branch: %s)",
            len(metadata.files),
            owner,
            name,
            repo.default_branch,
        )

        return metadata

    # -----------------------------------------------------------------------
    # URL parsing
    # -----------------------------------------------------------------------

    def _parse_url(self, url: str) -> tuple[str, str]:
        """
        Extract owner and repo name from GitHub URL.
        """

        url = url.strip().rstrip("/")

        # FIXED:
        # avoid broken rstrip(".git") behavior
        if url.endswith(".git"):
            url = url[:-4]

        prefix = "https://github.com/"

        if not url.startswith(prefix):

            raise ValueError(
                f"Invalid GitHub URL: {url!r}. "
                "Expected format: https://github.com/owner/repo"
            )

        parts = url.replace(prefix, "").split("/")

        if len(parts) < 2:

            raise ValueError(
                f"Invalid GitHub URL: {url!r}. "
                "Expected format: https://github.com/owner/repo"
            )

        owner = parts[0].strip()
        repo = parts[1].strip()

        if not owner or not repo:

            raise ValueError(
                f"Invalid GitHub URL: {url!r}"
            )

        return owner, repo

    # -----------------------------------------------------------------------
    # File iteration
    # -----------------------------------------------------------------------

    def _iter_files(
        self,
        repo: Repository,
    ) -> Generator[RepoFile, None, None]:
        """
        Walk repository tree and yield parseable files.
        """

        try:

            tree = repo.get_git_tree(
                repo.default_branch,
                recursive=True,
            )

        except GithubException as e:

            logger.warning(
                "Could not get git tree: %s",
                e,
            )

            return

        count = 0

        max_size_bytes = (
            settings.max_file_size_kb * 1024
        )

        for item in tree.tree:

            try:

                if item.type != "blob":
                    continue

                parts = item.path.split("/")

                # Skip ignored paths
                if any(p in SKIP_PATHS for p in parts):
                    continue

                _, ext = _splitext(item.path)

                language = SUPPORTED_EXTENSIONS.get(ext)

                if not language:
                    continue

                # Skip oversized files
                if item.size and item.size > max_size_bytes:

                    logger.debug(
                        "Skipping oversized file: %s (%d bytes)",
                        item.path,
                        item.size,
                    )

                    continue

                content = self._fetch_content(
                    repo,
                    item.path,
                )

                if content is None:
                    continue

                yield RepoFile(
                    path=item.path,
                    language=language,
                    content=content,
                    size_bytes=len(content.encode("utf-8")),
                )

                count += 1

                if count >= settings.max_files_per_repo:

                    logger.info(
                        "Hit MAX_FILES_PER_REPO limit (%d)",
                        settings.max_files_per_repo,
                    )

                    break

            except Exception as e:

                logger.warning(
                    "Error processing file %s: %s",
                    getattr(item, "path", "unknown"),
                    e,
                )

                continue

    # -----------------------------------------------------------------------
    # Content fetching
    # -----------------------------------------------------------------------

    def _fetch_content(
        self,
        repo: Repository,
        path: str,
    ) -> str | None:
        """
        Fetch and decode file content.
        """

        try:

            file_obj = repo.get_contents(path)

            if isinstance(file_obj, list):
                return None

            raw = file_obj.content

            if file_obj.encoding == "base64":

                return base64.b64decode(raw).decode(
                    "utf-8",
                    errors="replace",
                )

            return raw

        except (GithubException, UnicodeDecodeError) as e:

            logger.debug(
                "Could not fetch %s: %s",
                path,
                e,
            )

            return None


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def _splitext(path: str) -> tuple[str, str]:
    """
    Split path into (stem, extension).
    """

    dot = path.rfind(".")

    if dot == -1:
        return path, ""

    return path[:dot], path[dot:]