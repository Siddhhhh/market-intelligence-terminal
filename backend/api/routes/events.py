"""
Market Events API Routes

GET /api/events — retrieve detected market events with filtering
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel

from backend.api.dependencies import get_db

router = APIRouter(prefix="/api/events", tags=["Events"])


class MarketEventResponse(BaseModel):
    id: int
    date: str
    event_type: str
    severity: str
    entity_type: Optional[str] = None
    ticker: Optional[str] = None
    magnitude: Optional[float] = None
    description: Optional[str] = None


@router.get("", response_model=list[MarketEventResponse])
def list_events(
    event_type: Optional[str] = Query(None, description="price_spike, price_crash, market_crash, sector_move"),
    severity: Optional[str] = Query(None, description="low, medium, high, critical"),
    ticker: Optional[str] = Query(None, description="Filter by ticker"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    Retrieve detected market events.

    Supports filtering by event type, severity, ticker, and date range.
    Returns most recent events first.
    """
    query = "SELECT id, date::date, event_type, severity, entity_type, ticker, magnitude, description FROM market_events WHERE 1=1"
    params: dict = {}

    if event_type:
        query += " AND event_type = :event_type"
        params["event_type"] = event_type

    if severity:
        query += " AND severity = :severity"
        params["severity"] = severity

    if ticker:
        query += " AND ticker = :ticker"
        params["ticker"] = ticker.upper()

    if start_date:
        query += " AND date >= :start_date"
        params["start_date"] = start_date

    if end_date:
        query += " AND date <= :end_date"
        params["end_date"] = end_date

    query += " ORDER BY date DESC LIMIT :limit OFFSET :offset"
    params["limit"] = limit
    params["offset"] = offset

    rows = db.execute(text(query), params).fetchall()

    return [
        MarketEventResponse(
            id=r[0], date=str(r[1]), event_type=r[2], severity=r[3],
            entity_type=r[4], ticker=r[5],
            magnitude=float(r[6]) if r[6] else None,
            description=r[7],
        )
        for r in rows
    ]
