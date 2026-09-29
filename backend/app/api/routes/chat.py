from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser
from app.chat.bot import CineBot
from app.core.config import get_settings
from app.db.session import SessionDep

router = APIRouter(tags=["chat"])

MAX_HISTORY = 20


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1)


class ChatResponse(BaseModel):
    answer: str
    tools_used: list[str]


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest, user: CurrentUser, session: SessionDep) -> dict:
    if not get_settings().groq_api_key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Chatbot is not configured")
    if body.messages[-1].role != "user":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Last message must be from the user")
    history = [m.model_dump() for m in body.messages[-MAX_HISTORY:]]
    return await CineBot(session, user.id).reply(history, user.display_name)
