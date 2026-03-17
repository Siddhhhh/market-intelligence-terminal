"""
Market Overview API Routes

GET /api/market/overview   — market summary (index proxies, VIX, top movers)
GET /api/market/suggestions — AI-powered stock suggestions based on momentum
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel

from backend.api.dependencies import get_db

router = APIRouter(prefix="/api/market", tags=["Market Overview"])


class MarketOverview(BaseModel):
    market_date: str
    sp500_proxy_change: Optional[float] = None
    vix_level: Optional[float] = None
    total_companies: int = 0
    advancing: int = 0
    declining: int = 0
    top_gainers: list[dict] = []
    top_losers: list[dict] = []


class StockSuggestion(BaseModel):
    ticker: str
    name: str
    sector: Optional[str] = None
    close: float
    weekly_return: Optional[float] = None
    monthly_return: Optional[float] = None
    signal: str
    reason: str


@router.get("/overview", response_model=MarketOverview)
def market_overview(db: Session = Depends(get_db)):
    """
    Get a market summary for the latest trading day.
    Includes advance/decline ratio, VIX, and top 3 movers.
    """
    # Latest trading date
    date_row = db.execute(text("SELECT MAX(date)::date FROM stocks")).fetchone()
    latest_date = str(date_row[0]) if date_row and date_row[0] else "N/A"

    # Advance/Decline
    ad_row = db.execute(text("""
        SELECT
            COUNT(*) FILTER (WHERE pct_change > 0) as advancing,
            COUNT(*) FILTER (WHERE pct_change < 0) as declining,
            COUNT(*) as total
        FROM stocks
        WHERE date::date = :date AND pct_change IS NOT NULL
    """), {"date": latest_date}).fetchone()

    # SP500 proxy: average change of all stocks that day
    sp500_row = db.execute(text("""
        SELECT ROUND(AVG(pct_change)::numeric, 4)
        FROM stocks s
        JOIN companies c ON s.company_id = c.id
        WHERE s.date::date = :date AND c.is_sp500 = TRUE AND s.pct_change IS NOT NULL
    """), {"date": latest_date}).fetchone()

    # VIX
    vix_row = db.execute(text("""
        SELECT value FROM macro_events
        WHERE indicator = 'vix'
        ORDER BY date DESC LIMIT 1
    """)).fetchone()

    # Top 3 gainers/losers
    gainers = db.execute(text("""
        SELECT c.ticker, c.name, s.pct_change
        FROM stocks s JOIN companies c ON s.company_id = c.id
        WHERE s.date::date = :date AND s.pct_change IS NOT NULL
        ORDER BY s.pct_change DESC LIMIT 3
    """), {"date": latest_date}).fetchall()

    losers = db.execute(text("""
        SELECT c.ticker, c.name, s.pct_change
        FROM stocks s JOIN companies c ON s.company_id = c.id
        WHERE s.date::date = :date AND s.pct_change IS NOT NULL
        ORDER BY s.pct_change ASC LIMIT 3
    """), {"date": latest_date}).fetchall()

    return MarketOverview(
        market_date=latest_date,
        sp500_proxy_change=float(sp500_row[0]) if sp500_row and sp500_row[0] else None,
        vix_level=float(vix_row[0]) if vix_row else None,
        total_companies=ad_row[2] if ad_row else 0,
        advancing=ad_row[0] if ad_row else 0,
        declining=ad_row[1] if ad_row else 0,
        top_gainers=[
            {"ticker": r[0], "name": r[1], "pct_change": float(r[2])} for r in gainers
        ],
        top_losers=[
            {"ticker": r[0], "name": r[1], "pct_change": float(r[2])} for r in losers
        ],
    )


@router.get("/suggestions", response_model=list[StockSuggestion])
def stock_suggestions(
    limit: int = Query(8, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """
    AI-powered stock suggestions based on recent momentum.

    Finds stocks with strong positive momentum over the past week and month,
    filtering for consistent performers (not one-day spikes).
    """
    rows = db.execute(text("""
        WITH recent AS (
            SELECT
                c.ticker,
                c.name,
                sec.display_name as sector,
                -- Latest close
                (SELECT close FROM stocks WHERE company_id = c.id ORDER BY date DESC LIMIT 1) as latest_close,
                -- 5-day return
                ROUND((
                    (SELECT close FROM stocks WHERE company_id = c.id ORDER BY date DESC LIMIT 1) /
                    NULLIF((SELECT close FROM stocks WHERE company_id = c.id ORDER BY date DESC LIMIT 1 OFFSET 5), 0)
                    - 1) * 100::numeric, 2
                ) as week_return,
                -- 21-day return (approx 1 month)
                ROUND((
                    (SELECT close FROM stocks WHERE company_id = c.id ORDER BY date DESC LIMIT 1) /
                    NULLIF((SELECT close FROM stocks WHERE company_id = c.id ORDER BY date DESC LIMIT 1 OFFSET 21), 0)
                    - 1) * 100::numeric, 2
                ) as month_return
            FROM companies c
            JOIN sectors sec ON c.sector_id = sec.id
            WHERE c.is_active = TRUE AND c.is_sp500 = TRUE
        )
        SELECT ticker, name, sector, latest_close, week_return, month_return
        FROM recent
        WHERE week_return IS NOT NULL AND month_return IS NOT NULL
            AND week_return > 0 AND month_return > 2
        ORDER BY month_return DESC
        LIMIT :limit
    """), {"limit": limit}).fetchall()

    suggestions = []
    for r in rows:
        week_ret = float(r[4]) if r[4] else 0
        month_ret = float(r[5]) if r[5] else 0

        if month_ret > 15:
            signal = "strong_momentum"
            reason = f"Up {month_ret:+.1f}% this month with sustained weekly gains"
        elif month_ret > 8:
            signal = "momentum"
            reason = f"Solid {month_ret:+.1f}% monthly return, {week_ret:+.1f}% this week"
        else:
            signal = "positive_trend"
            reason = f"Steady uptrend: {month_ret:+.1f}% monthly, {week_ret:+.1f}% weekly"

        suggestions.append(StockSuggestion(
            ticker=r[0],
            name=r[1],
            sector=r[2],
            close=float(r[3]) if r[3] else 0,
            weekly_return=week_ret,
            monthly_return=month_ret,
            signal=signal,
            reason=reason,
        ))

    return suggestions
