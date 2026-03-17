"""
Stock API Routes

GET /api/stocks          — list companies or search by ticker
GET /api/stocks/{ticker} — price history for a single ticker
"""

from datetime import datetime, date
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel

from backend.api.dependencies import get_db

router = APIRouter(prefix="/api/stocks", tags=["Stocks"])


# ── Response Models ─────────────────────────────────────────

class CompanyResponse(BaseModel):
    id: int
    ticker: str
    name: str
    sector: Optional[str] = None
    industry: Optional[str] = None
    is_sp500: bool

class StockPriceResponse(BaseModel):
    date: str
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: float
    volume: Optional[int] = None
    pct_change: Optional[float] = None

class StockHistoryResponse(BaseModel):
    ticker: str
    company_name: str
    total_records: int
    data: list[StockPriceResponse]


# ── Endpoints ───────────────────────────────────────────────

@router.get("", response_model=list[CompanyResponse])
def list_companies(
    search: Optional[str] = Query(None, description="Search by ticker or name"),
    sector: Optional[str] = Query(None, description="Filter by sector name"),
    sp500_only: bool = Query(False, description="Only S&P 500 companies"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List companies with optional search and sector filtering."""
    query = """
        SELECT c.id, c.ticker, c.name, s.display_name as sector, c.industry, c.is_sp500
        FROM companies c
        LEFT JOIN sectors s ON c.sector_id = s.id
        WHERE c.is_active = TRUE
    """
    params = {}

    if search:
        query += " AND (c.ticker ILIKE :search OR c.name ILIKE :search)"
        params["search"] = f"%{search}%"

    if sector:
        query += " AND s.name = :sector"
        params["sector"] = sector

    if sp500_only:
        query += " AND c.is_sp500 = TRUE"

    query += " ORDER BY c.ticker LIMIT :limit OFFSET :offset"
    params["limit"] = limit
    params["offset"] = offset

    rows = db.execute(text(query), params).fetchall()

    return [
        CompanyResponse(
            id=r[0], ticker=r[1], name=r[2],
            sector=r[3], industry=r[4], is_sp500=r[5],
        )
        for r in rows
    ]


@router.get("/{ticker}", response_model=StockHistoryResponse)
def get_stock_history(
    ticker: str,
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(1000, ge=1, le=10000),
    db: Session = Depends(get_db),
):
    """Get price history for a specific stock ticker."""
    ticker = ticker.upper()

    # Get company info
    company = db.execute(text(
        "SELECT id, ticker, name FROM companies WHERE ticker = :ticker"
    ), {"ticker": ticker}).fetchone()

    if not company:
        raise HTTPException(status_code=404, detail=f"Ticker '{ticker}' not found")

    company_id = company[0]

    # Build price query
    query = """
        SELECT date::date, open, high, low, close, volume, pct_change
        FROM stocks
        WHERE company_id = :company_id
    """
    params: dict = {"company_id": company_id}

    if start_date:
        query += " AND date >= :start_date"
        params["start_date"] = start_date

    if end_date:
        query += " AND date <= :end_date"
        params["end_date"] = end_date

    query += " ORDER BY date DESC LIMIT :limit"
    params["limit"] = limit

    rows = db.execute(text(query), params).fetchall()

    data = [
        StockPriceResponse(
            date=str(r[0]), open=float(r[1]) if r[1] else None,
            high=float(r[2]) if r[2] else None,
            low=float(r[3]) if r[3] else None,
            close=float(r[4]),
            volume=int(r[5]) if r[5] else None,
            pct_change=float(r[6]) if r[6] else None,
        )
        for r in rows
    ]

    return StockHistoryResponse(
        ticker=company[1],
        company_name=company[2],
        total_records=len(data),
        data=data,
    )
