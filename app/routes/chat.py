from fastapi import APIRouter, Depends, HTTPException
from typing import List
from pydantic import BaseModel
from app.utils.dependencies import get_current_user
from app.models import User
from app.services.ai_service import process_chat

router = APIRouter()

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = []

class ChatResponse(BaseModel):
    reply: str

@router.post("/", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest, current_user: User = Depends(get_current_user)):
    try:
        # history in format [ {"role": "user", "content": "..."}, ... ]
        history_dicts = [{"role": msg.role, "content": msg.content} for msg in req.history]
        reply = process_chat(req.message, history_dicts, current_user.id)
        if reply.startswith("Error connecting to AI Assistant:"):
            raise HTTPException(status_code=500, detail=reply)
        return ChatResponse(reply=reply)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing chat: {str(e)}")