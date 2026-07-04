from fastapi import APIRouter, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.config import settings

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


@router.get("/{repo_id}")
@limiter.limit(settings.rate_walkthrough)
async def get_walkthrough(request: Request, repo_id: str):
    """
    Week 3: LangGraph pipeline generates an ordered reading path
    for new developers, with plain-English file descriptions.
    """
    return {
        "steps": [],
        "message": "Onboarding Walkthrough will be implemented in Week 3",
        "repo_id": repo_id,
    }
