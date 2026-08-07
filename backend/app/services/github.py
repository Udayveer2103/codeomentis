from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from github import Github
from github.ContentFile import ContentFile

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
        self.client = Github(settings.github_token)

    def fetch_repo(self, github_url: str) -> RepoMeta:
        """
        Fetch repository contents from GitHub.

        Supports:
        - https://github.com/owner/repo
        - https://github.com/owner/repo/
        - https://github.com/owner/repo.git

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

        repo = self.client.get_repo(repo_name)

        files: List[RepoFile] = []
        config_files: List[RepoFile] = []

        contents = repo.get_contents("")

        while contents:
            item = contents.pop(0)

            if item.type == "dir":
                contents.extend(repo.get_contents(item.path))
                continue

            language = self._detect_language(item.path)

            if language:
                try:
                    decoded = item.decoded_content.decode("utf-8")

                    files.append(
                        RepoFile(
                            path=item.path,
                            content=decoded,
                            language=language,
                        )
                    )

                except Exception:
                    continue

                continue

            if self._is_config_file(item.path):
                try:
                    if item.size > MAX_CONFIG_FILE_BYTES:
                        # Record the file without content — still useful
                        # for "this file exists" analysis, just not for
                        # parsing its contents.
                        config_files.append(
                            RepoFile(
                                path=item.path,
                                content="",
                                language="config",
                            )
                        )
                        continue

                    decoded = item.decoded_content.decode("utf-8")

                    config_files.append(
                        RepoFile(
                            path=item.path,
                            content=decoded,
                            language="config",
                        )
                    )

                except Exception:
                    continue

        return RepoMeta(
            owner=repo.owner.login,
            name=repo.name,
            default_branch=repo.default_branch,
            language_stats=repo.get_languages(),
            files=files,
            config_files=config_files,
        )

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