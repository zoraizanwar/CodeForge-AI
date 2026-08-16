import os
import httpx
import secrets
from typing import Dict, Any, Tuple
from fastapi import HTTPException

class OAuthService:
    @staticmethod
    def get_github_authorize_url(state: str, redirect_uri: str) -> str:
        client_id = os.environ.get("GITHUB_APP_CLIENT_ID")
        if not client_id:
            raise HTTPException(status_code=500, detail="GitHub OAuth not configured")
            
        return f"https://github.com/login/oauth/authorize?client_id={client_id}&state={state}&redirect_uri={redirect_uri}&scope=user:email"

    @staticmethod
    async def exchange_github_code(code: str, redirect_uri: str) -> str:
        client_id = os.environ.get("GITHUB_APP_CLIENT_ID")
        client_secret = os.environ.get("GITHUB_APP_CLIENT_SECRET")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://github.com/login/oauth/access_token",
                json={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri
                },
                headers={"Accept": "application/json"}
            )
            data = response.json()
            if "error" in data:
                raise HTTPException(status_code=400, detail="Failed to exchange code")
            return data["access_token"]

    @staticmethod
    async def get_github_user(access_token: str) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.github.com/user",
                headers={"Authorization": f"token {access_token}"}
            )
            if response.status_code != 200:
                raise HTTPException(status_code=400, detail="Failed to fetch GitHub user")
            return response.json()
