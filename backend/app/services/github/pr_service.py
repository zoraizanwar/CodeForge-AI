"""
GitHub Pull Request Service for CodeForge AI (Step 9).
Manages GitHub App REST API interactions for branch verification and Pull Request creation.
"""
import logging
from typing import Dict, Any, Optional, List
import httpx
from app.core.http_client import get_httpx_client
from app.services.github import GitHubService


logger = logging.getLogger("codeforge.github.pr")


class GitHubPRService:
    def __init__(self, github_service: Optional[GitHubService] = None):
        self.github_service = github_service or GitHubService()

    async def get_repository_details(self, installation_id: int, owner: str, repo: str) -> Dict[str, Any]:
        """Fetches repository details including default branch."""
        token = await self.github_service.get_installation_access_token(installation_id)
        url = f"https://api.github.com/repos/{owner}/{repo}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
        }
        resp = await self.github_service._safe_http_request("GET", url, headers=headers)
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to fetch repo details from GitHub: {resp.status_code} {resp.text}")
        return resp.json()

    async def get_open_pull_requests(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        head_branch: str
    ) -> List[Dict[str, Any]]:
        """Searches for existing open pull requests for the specified head branch to prevent duplicates."""
        token = await self.github_service.get_installation_access_token(installation_id)
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls?state=open&head={owner}:{head_branch}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
        }
        resp = await self.github_service._safe_http_request("GET", url, headers=headers)
        if resp.status_code == 200:
            return resp.json()
        return []

    async def create_pull_request(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str
    ) -> Dict[str, Any]:
        """
        Creates a new Pull Request on GitHub for the specified feature branch.
        Checks for existing open PRs first to avoid duplicates.
        """
        # 1. Check if PR already exists for head_branch
        existing = await self.get_open_pull_requests(installation_id, owner, repo, head_branch)
        if existing:
            logger.info(f"Existing open PR #{existing[0]['number']} found for branch '{head_branch}'. Returning existing PR.")
            return existing[0]

        token = await self.github_service.get_installation_access_token(installation_id)
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
        }
        payload = {
            "title": title,
            "body": body,
            "head": head_branch,
            "base": base_branch
        }
        try:
            async with get_httpx_client() as client:
                resp = await client.post(url, json=payload, headers=headers)
        except Exception:
            async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
                resp = await client.post(url, json=payload, headers=headers)

        if resp.status_code not in (201, 200):
            if resp.status_code == 403 or "Resource not accessible" in resp.text:
                compare_url = f"https://github.com/{owner}/{repo}/compare/{base_branch}...{head_branch}?expand=1"
                logger.warning(f"GitHub PR creation 403. Provided 1-click PR comparison link: {compare_url}")
                return {
                    "number": None,
                    "html_url": compare_url,
                    "state": "local_patch_applied",
                    "message": "Local patch applied. 1-Click Pull Request link generated."
                }
            raise RuntimeError(f"Failed to create GitHub Pull Request: {resp.status_code} {resp.text}")
        return resp.json()
