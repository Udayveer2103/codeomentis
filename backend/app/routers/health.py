from fastapi import APIRouter
from datetime import datetime, timezone

router = APIRouter()


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "repomind-api",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
