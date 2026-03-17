"""
AI Chat API Routes

POST /api/ai/chat — send a question to the AI market analyst

Full pipeline:
    User Question → Query Router (Mistral) → Evidence Builder → Market Analyst (Llama3) → Response
"""

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from loguru import logger

from backend.api.dependencies import get_db
from backend.ai_engine.analyst import analyze_question

router = APIRouter(prefix="/api/ai", tags=["AI Analyst"])


class ChatRequest(BaseModel):
    question: str
    context: Optional[str] = None

class EvidenceSummary(BaseModel):
    tickers_analyzed: list[str] = []
    events_found: int = 0
    macro_points: int = 0
    signals_used: int = 0
    data_points: int = 0

class ChatResponse(BaseModel):
    question: str
    category: str
    answer: str
    evidence_summary: EvidenceSummary
    sources_used: list[str]
    confidence: float
    processing_time: float


@router.post("/chat", response_model=ChatResponse)
def ai_chat(request: ChatRequest, db: Session = Depends(get_db)):
    """
    Ask the AI market analyst a question about financial markets.

    The system:
    1. Routes your question through Mistral (intent classification)
    2. Builds evidence by querying the database (stocks, events, macro)
    3. Generates an answer using Llama3 grounded in real data

    Example questions:
    - "Why did NVIDIA rise in 2023?"
    - "What caused the 2008 financial crisis?"
    - "Which sectors performed best during COVID?"
    - "What is inflation?"
    """
    logger.info(f"AI Chat: '{request.question[:80]}'")

    result = analyze_question(request.question)

    return ChatResponse(
        question=result["question"],
        category=result["category"],
        answer=result["answer"],
        evidence_summary=EvidenceSummary(**result.get("evidence_summary", {})),
        sources_used=result["sources_used"],
        confidence=result["confidence"],
        processing_time=result["processing_time"],
    )
