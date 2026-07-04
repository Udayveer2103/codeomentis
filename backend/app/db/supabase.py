"""
Supabase service client — used by backend services (not the frontend).

Uses the SERVICE ROLE KEY which bypasses RLS. Only use this on the backend
where user ownership is verified in application code before any write.

Week 2 addition: get_user_from_token() validates a frontend JWT and returns
the Supabase user, used for auth in API endpoints.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache

from supabase import Client, create_client

from app.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    """
    Return a cached Supabase service-role client.

    lru_cache(1) means this is effectively a singleton — one client
    for the lifetime of the process, which is correct for FastAPI.
    """
    return create_client(
        settings.supabase_url,
        settings.supabase_service_key,
    )


@dataclass
class AuthUser:
    id: str
    email: str


async def get_user_from_token(token: str) -> AuthUser | None:
    """
    Validate a Supabase JWT and return the user.

    Uses the Supabase auth.get_user() endpoint with the user's own token.
    This is the correct way to validate tokens — don't decode JWTs manually.

    Returns None if the token is invalid or expired.
    """
    try:
        # Create a temporary client with the user's token to validate it
        client = create_client(settings.supabase_url, settings.supabase_service_key)
        response = client.auth.get_user(token)
        user = response.user
        if not user:
            return None
        return AuthUser(id=str(user.id), email=user.email or "")
    except Exception as e:
        logger.debug("Token validation failed: %s", e)
        return None