import os
from typing import Self
from github import Github, GithubIntegration
from github.Auth import AppAuth


class GitHubTools:
    def create() -> Self | None:
        GITHUB_APP_ID = os.environ.get("GITHUB_APP_ID")
        GITHUB_APP_PRIVATE_KEY = os.environ.get("GITHUB_APP_PRIVATE_KEY")
        if GITHUB_APP_ID is None or GITHUB_APP_PRIVATE_KEY is None:
            return None

        gh = GithubIntegration(auth=AppAuth(GITHUB_APP_ID, GITHUB_APP_PRIVATE_KEY))
        gi = gh.get_installations().get_page(0)[0]

        return GitHubTools(gi.get_github_for_installation())

    def __init__(self, gh: Github):
        self.github = gh

    def _get_repo(self, repo_name: str):
        return self.github.get_repo(repo_name)

    def get_github_files(self, repo: str, ref: str = "", path: str = "") -> list[str]:
        """Get file list from repository. Return file / directory list.
        List is formatted as `<type> <name> <size>`. e.g. `file README.md 1221`

        Parameters
        ----------
        repo : str
            Repository name. Consists of owner and repository name. e.g. "{owner}/{repo}"
            Do not include ".git" at the end of the repository name.
        ref : str, optional
            Branch name, by default empty and return default branch files
        path : str, optional
            Path to get files, by default empty and return root files

        Returns
        -------
        List[str]
            List of file / directory in the repository
        """
        repo = self._get_repo(repo)
        ref = ref if ref != "" else repo.default_branch
        contents = repo.get_contents(path, ref)
        return "\n".join(
            [f"{content.type} {content.name} {content.size}" for content in contents]
        )
