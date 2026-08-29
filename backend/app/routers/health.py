from fastapi import APIRouter
from datetime import datetime, timezone

router = APIRouter()


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "codeomentis-api",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
