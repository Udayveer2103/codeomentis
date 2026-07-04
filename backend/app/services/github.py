from __future__ import annotations

from dataclasses import dataclass
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
        """

        github_url = github_url.strip().rstrip("/")

        # Remove .git suffix if present
        if github_url.endswith(".git"):
            github_url = github_url[:-4]

        repo_name = github_url.replace(
            "https://github.com/",
            ""
        )

        repo = self.client.get_repo(repo_name)

        files: List[RepoFile] = []

        contents = repo.get_contents("")

        while contents:
            item = contents.pop(0)

            if item.type == "dir":
                contents.extend(repo.get_contents(item.path))
                continue

            language = self._detect_language(item.path)

            if not language:
                continue

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

        return RepoMeta(
            owner=repo.owner.login,
            name=repo.name,
            default_branch=repo.default_branch,
            language_stats=repo.get_languages(),
            files=files,
        )

    def _detect_language(self, path: str) -> str:
        for ext, language in SUPPORTED_EXTENSIONS.items():
            if path.endswith(ext):
                return language
        return ""