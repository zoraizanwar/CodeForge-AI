import os
import time
import logging
from typing import Dict, Any, List, Optional, Union

import httpx
import jwt
from app.core.config import settings
from app.core.http_client import get_httpx_client

logger = logging.getLogger(__name__)

class GitHubService:
    def __init__(
        self,
        app_id: Optional[int] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        private_key_path: Optional[str] = None
    ):
        self.app_id = app_id or settings.GITHUB_APP_ID
        self.client_id = client_id or settings.GITHUB_CLIENT_ID
        self.client_secret = client_secret or settings.GITHUB_CLIENT_SECRET
        self.private_key_path = private_key_path or settings.github_private_key_resolved_path

        # If any of these are missing in non-testing mode, fail during execution of services
        if not self.app_id or not self.client_id or not self.client_secret or not self.private_key_path:
            raise ValueError(
                "Required GitHub App configurations (GITHUB_APP_ID, GITHUB_CLIENT_ID, "
                "GITHUB_CLIENT_SECRET, or GITHUB_PRIVATE_KEY_PATH) are not configured."
            )

        if not os.path.exists(self.private_key_path):
            raise ValueError(f"GitHub App private key file not found at: {self.private_key_path}")

    def _load_private_key(self) -> str:
        """Loads and returns the private key content from the configured file path."""
        try:
            with open(self.private_key_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.error("Failed to read GitHub private key file.")
            raise ValueError("Failed to load private key file.") from e

    def generate_app_jwt(self) -> str:
        """Generates a short-lived JWT for authenticating as the GitHub App using RS256."""
        private_key = self._load_private_key()
        now = int(time.time())
        payload = {
            "iat": now - 60,      # Issued 60 seconds ago to account for clock skew
            "exp": now + 540,     # Expiration: 9 minutes from issue time (maximum is 10 min)
            "iss": str(self.app_id)    # Issuer: GitHub App ID
        }
        try:
            token = jwt.encode(payload, private_key, algorithm="RS256")
            return token
        except Exception as e:
            logger.error("Failed to generate GitHub App JWT.")
            raise RuntimeError("Failed to generate App JWT.") from e

    async def _safe_http_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        follow_redirects: bool = False
    ) -> httpx.Response:
        """
        Executes HTTP request with SSL verification, falling back to unverified SSL
        if Windows certificate store verification fails.
        """
        try:
            async with get_httpx_client(follow_redirects=follow_redirects) as client:
                if method.upper() == "POST":
                    return await client.post(url, headers=headers, params=params)
                return await client.get(url, headers=headers, params=params)
        except Exception as ssl_err:
            logger.warning(f"SSL or connection error connecting to {url}: {str(ssl_err)}. Retrying with verify=False fallback.")

            async with httpx.AsyncClient(verify=False, timeout=30.0, follow_redirects=follow_redirects) as fallback_client:
                if method.upper() == "POST":
                    return await fallback_client.post(url, headers=headers, params=params)
                return await fallback_client.get(url, headers=headers, params=params)

    async def get_installation_access_token(self, installation_id: int) -> str:
        """Exchanges the GitHub App JWT for a short-lived installation access token."""
        app_jwt = self.generate_app_jwt()
        url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
        headers = {
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github.v3+json"
        }
        try:
            response = await self._safe_http_request("POST", url, headers=headers)
            if response.status_code != 201:
                logger.error(f"GitHub token exchange failed with status {response.status_code}: {response.text}")
                raise RuntimeError("Failed to obtain installation access token from GitHub.")
            data = response.json()
            return data["token"]
        except httpx.RequestError as e:
            logger.error("Network error while connecting to GitHub API for token exchange.")
            raise RuntimeError("Network error connecting to GitHub API.") from e

    async def exchange_code_for_user_token(self, code: str) -> str:
        """Exchanges OAuth code for a GitHub user access token."""
        url = "https://github.com/login/oauth/access_token"
        headers = {"Accept": "application/json"}
        params = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code
        }
        resp = await self._safe_http_request("POST", url, headers=headers, params=params)
        if resp.status_code != 200:
            raise RuntimeError(f"GitHub OAuth token exchange failed: {resp.text}")
        data = resp.json()
        if "access_token" not in data:
            raise RuntimeError(f"GitHub OAuth error: {data.get('error_description', 'No access token returned')}")
        return data["access_token"]

    async def get_authenticated_user(self, user_token: str) -> Dict[str, Any]:
        """Fetches the authenticated user profile from GitHub API."""
        url = "https://api.github.com/user"
        headers = {
            "Authorization": f"Bearer {user_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        resp = await self._safe_http_request("GET", url, headers=headers)
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to fetch GitHub user profile: {resp.text}")
        return resp.json()

    async def get_installation_details(self, installation_id: int) -> Dict[str, Any]:
        """Fetches installation details from GitHub App API."""
        app_jwt = self.generate_app_jwt()
        url = f"https://api.github.com/app/installations/{installation_id}"
        headers = {
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github.v3+json"
        }
        resp = await self._safe_http_request("GET", url, headers=headers)
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to fetch installation details: {resp.text}")
        return resp.json()

    async def list_app_installations(self) -> List[Dict[str, Any]]:
        """Lists all installations of this GitHub App from GitHub API."""
        app_jwt = self.generate_app_jwt()
        url = "https://api.github.com/app/installations"
        headers = {
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github.v3+json"
        }
        resp = await self._safe_http_request("GET", url, headers=headers)
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to list GitHub App installations: {resp.text}")
        return resp.json()


    async def list_installation_repositories(
        self,
        installation_id: int,
        page: int = 1,
        per_page: int = 30
    ) -> Dict[str, Any]:
        """
        Lists all repositories accessible to the specified GitHub App installation.
        Returns the raw GitHub response dictionary containing total_count and repositories array.
        """
        token = await self.get_installation_access_token(installation_id)
        url = f"https://api.github.com/installation/repositories?page={page}&per_page={per_page}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        try:
            response = await self._safe_http_request("GET", url, headers=headers)
            if response.status_code != 200:
                logger.error(f"Failed to list installation repositories: status {response.status_code} {response.text}")
                raise RuntimeError(f"Failed to list repositories from GitHub: {response.status_code}")
            
            return response.json()
        except httpx.RequestError as e:
            logger.error("Network error while fetching installation repositories.")
            raise RuntimeError("Network error connecting to GitHub API.") from e


    # Alias for backwards compatibility with test suites
    list_repositories = list_installation_repositories

    async def get_repository(
        self,
        installation_id: int,
        owner: Union[str, int],
        repo: Optional[str] = None
    ) -> Dict[str, Any]:
        """Fetches repository details by owner & repo name OR by numeric repository ID."""
        token = await self.get_installation_access_token(installation_id)
        if repo is None:
            url = f"https://api.github.com/repositories/{owner}"
        else:
            url = f"https://api.github.com/repos/{owner}/{repo}"

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        resp = await self._safe_http_request("GET", url, headers=headers)
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to fetch repository metadata: {resp.text}")
        return resp.json()


    async def download_repository_zipball(
        self,
        installation_id: int,
        owner: str,
        repo: str,
        ref: Optional[str] = None
    ) -> bytes:
        """Downloads the source code archive (zipball) for a repository."""
        token = await self.get_installation_access_token(installation_id)
        url = f"https://api.github.com/repos/{owner}/{repo}/zipball"
        if ref:
            url = f"{url}/{ref}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        resp = await self._safe_http_request("GET", url, headers=headers, follow_redirects=True)
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to download repository zipball: {resp.status_code}")
        return resp.content
