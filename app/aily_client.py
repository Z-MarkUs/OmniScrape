import os
import time
import requests
from typing import Dict, Any, List, Optional


class AilyAuth:
    """Handles Aily auth token retrieval and caching."""

    _cached_token: Optional[str] = None
    _expires_at: float = 0.0

    @classmethod
    def get_access_token(cls) -> str:
        app_id = os.getenv("AILY_APP_ID")
        app_secret = os.getenv("AILY_APP_SECRET")
        base_url = os.getenv("AILY_BASE_URL", "https://open.aily.ai")

        if not app_id or not app_secret:
            raise RuntimeError("Missing AILY_APP_ID or AILY_APP_SECRET")

        now = time.time()
        if cls._cached_token and now < cls._expires_at - 60:
            return cls._cached_token

        # Common Feishu/Lark style tenant access token endpoint pattern; allow override via env
        token_endpoint = os.getenv("AILY_TOKEN_ENDPOINT", f"{base_url}/open-apis/auth/v3/tenant_access_token/internal")

        resp = requests.post(token_endpoint, json={
            "app_id": app_id,
            "app_secret": app_secret,
        }, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        # Try multiple common shapes
        access_token = data.get("tenant_access_token") or data.get("access_token") or data.get("data", {}).get("access_token")
        expire_sec = data.get("expire", 3600)

        if not access_token:
            raise RuntimeError(f"Aily token response missing access token: {data}")

        cls._cached_token = access_token
        cls._expires_at = now + int(expire_sec)
        return access_token


def aily_chat(messages: List[Dict[str, str]]) -> Dict[str, Any]:
    """Call Aily chat/skill with provided conversation messages.

    messages: list of {role: "user"|"system"|"assistant", content: str}
    Returns dict with keys: content (str), usage (dict optional)
    """
    token = AilyAuth.get_access_token()

    base_url = os.getenv("AILY_BASE_URL", "https://open.aily.ai")
    spring_id = os.getenv("AILY_SPRING_ID") or os.getenv("AILY_SPRING")
    skill_id = os.getenv("AILY_SKILL_ID") or os.getenv("AILY_SKILL")

    if not spring_id or not skill_id:
        raise RuntimeError("Missing AILY_SPRING_ID or AILY_SKILL_ID")

    # Allow overriding endpoint
    chat_endpoint = os.getenv("AILY_CHAT_ENDPOINT", f"{base_url}/open-apis/aiy/spring/{spring_id}/skill/{skill_id}/chat")

    # Payload shape may vary by Aily; we follow a generic structure allowing system+history
    payload = {
        "messages": messages,
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    resp = requests.post(chat_endpoint, json=payload, headers=headers, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    # Try to extract text and usage in tolerant way
    content = (
        data.get("content")
        or data.get("message")
        or data.get("data", {}).get("content")
        or data.get("choices", [{}])[0].get("message", {}).get("content")
        or ""
    )
    usage = (
        data.get("usage")
        or data.get("data", {}).get("usage")
        or {}
    )

    return {"content": content, "usage": usage}


