from uuid import UUID

from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db

from app.schemas.Products import ProductCreate
from app.core.limiter import limiter
from app.mcp_server.mcp_client import chat

router = APIRouter(prefix="/Chat", tags=["Chat"])


@router.post("/assistant")
@limiter.limit("10/minute")
async def chat_with_assistant(
    request: Request, message: str, db: Session = Depends(get_db)
):
    response = await chat(message)
    return response
