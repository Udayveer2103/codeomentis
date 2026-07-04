from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from pydantic import BaseModel
from app.config import settings 
import asyncio
import json

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


class ChatRequest(BaseModel):
    repo_id: str
    message: str
    history: list[dict] = []

    def __init__(self, **data):
        super().__init__(**data)
        if len(self.message) > 2000:
            raise ValueError("Message must be under 2000 characters")


@router.post("")
@limiter.limit(settings.rate_chat)
async def chat(request: Request, body: ChatRequest):
    """
    Week 3: RAG chain — embeds the message, retrieves top-k code chunks,
    injects architecture context, streams LLM response via SSE.
    """
    async def stream():
        stub = "Chat with architecture-aware RAG will be implemented in Week 3."
        for word in stub.split():
            yield f"data: {json.dumps({'token': word + ' '})}\n\n"
            await asyncio.sleep(0.05)
        yield "data: [DONE]\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")
