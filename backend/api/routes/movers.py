"""
Top Movers API Routes (Enhanced)

GET /api/movers/gainers  — top gaining stocks or crypto
GET /api/movers/losers   — top losing stocks or crypto
GET /api/movers/summary  — both gainers and losers in one call

Supports periods: daily, weekly, monthly
Supports asset types: stock, crypto
"""

from typing import Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel

from backend.api.dependencies import get_db

router = APIRouter(prefix="/api/movers", tags=["Top Movers"])


class MoverResponse(BaseModel):
    ticker: str
    name: str
    sector: Optional[str] = None
    date: str
    close: float
    pct_change: float
    volume: Optional[int] = None
    period: str

class MoversSummaryResponse(BaseModel):
    period: str
    date: str
    gainers: list[MoverResponse]
    losers: list[MoverResponse]


PERIOD_CALENDAR_DAYS = {
    "daily": 0,
    "weekly": 10,
    "monthly": 45,
}


@router.get("/gainers", response_model=list[MoverResponse])
def top_gainers(
    period: str = Query("daily", description="daily, weekly, or monthly"),
    date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    asset_type: str = Query("stock", description="stock or crypto"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Top gaining stocks or crypto for the given period."""
    if asset_type == "crypto":
        return _get_crypto_movers(db, date, period, "DESC", limit)
    return _get_stock_movers(db, date, period, "DESC", limit)


@router.get("/losers", response_model=list[MoverResponse])
def top_losers(
    period: str = Query("daily", description="daily, weekly, or monthly"),
    date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    asset_type: str = Query("stock", description="stock or crypto"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Top losing stocks or crypto for the given period."""
    if asset_type == "crypto":
        return _get_crypto_movers(db, date, period, "ASC", limit)
    return _get_stock_movers(db, date, period, "ASC", limit)


@router.get("/summary", response_model=MoversSummaryResponse)
def movers_summary(
    period: str = Query("daily", description="daily, weekly, or monthly"),
    date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    asset_type: str = Query("stock", description="stock or crypto"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Get both gainers and losers in a single call."""
    if asset_type == "crypto":
        gainers = _get_crypto_movers(db, date, period, "DESC", limit)
        losers = _get_crypto_movers(db, date, period, "ASC", limit)
    else:
        gainers = _get_stock_movers(db, date, period, "DESC", limit)
        losers = _get_stock_movers(db, date, period, "ASC", limit)

    resolved_date = gainers[0].date if gainers else (losers[0].date if losers else "N/A")

    return MoversSummaryResponse(
        period=period, date=resolved_date, gainers=gainers, losers=losers,
    )


def _resolve_date(db: Session, table: str) -> Optional[str]:
    """Get the latest trading date from a table."""
    row = db.execute(text(f"SELECT MAX(date)::date FROM {table}")).fetchone()
    return str(row[0]) if row and row[0] else None


def _compute_lookback_date(end_date: str, period: str) -> str:
    """Compute the start date for a lookback period in Python (avoids SQL cast issues)."""
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    calendar_days = PERIOD_CALENDAR_DAYS.get(period, 10)
    start_dt = end_dt - timedelta(days=calendar_days)
    return start_dt.strftime("%Y-%m-%d")


# ── Stock movers ────────────────────────────────────────────

def _get_stock_movers(db, date, period, order, limit):
    if not date:
        date = _resolve_date(db, "stocks")
        if not date:
            return []

    if period == "daily":
        return _daily_stock_movers(db, date, order, limit)
    else:
        lookback_start = _compute_lookback_date(date, period)
        return _period_stock_movers(db, date, lookback_start, period, order, limit)


def _daily_stock_movers(db, date, order, limit):
    rows = db.execute(text(f"""
        SELECT c.ticker, c.name, sec.display_name, s.date::date, s.close, s.pct_change, s.volume
        FROM stocks s
        JOIN companies c ON s.company_id = c.id
        LEFT JOIN sectors sec ON c.sector_id = sec.id
        WHERE s.date::date = :date AND s.pct_change IS NOT NULL
        ORDER BY s.pct_change {order}
        LIMIT :limit
    """), {"date": date, "limit": limit}).fetchall()

    return [
        MoverResponse(
            ticker=r[0], name=r[1], sector=r[2], date=str(r[3]),
            close=float(r[4]), pct_change=float(r[5]),
            volume=int(r[6]) if r[6] else None, period="daily",
        )
        for r in rows
    ]


def _period_stock_movers(db, end_date, lookback_start, period, order, limit):
    """
    Compute weekly/monthly movers.
    Finds earliest close in the lookback window and latest close on end_date,
    then computes the return. All in one SQL query.
    """
    rows = db.execute(text(f"""
        WITH end_prices AS (
            SELECT s.company_id, s.close as end_close, s.volume
            FROM stocks s
            WHERE s.date::date = :end_date AND s.close IS NOT NULL
        ),
        start_prices AS (
            SELECT DISTINCT ON (s.company_id)
                s.company_id, s.close as start_close
            FROM stocks s
            WHERE s.date::date >= :lookback_start
            AND s.date::date < :end_date
            AND s.close IS NOT NULL
            ORDER BY s.company_id, s.date ASC
        )
        SELECT
            c.ticker,
            c.name,
            sec.display_name,
            :end_date as end_date,
            ep.end_close,
            ROUND(((ep.end_close - sp.start_close) / NULLIF(sp.start_close, 0) * 100)::numeric, 2),
            ep.volume
        FROM end_prices ep
        JOIN start_prices sp ON ep.company_id = sp.company_id
        JOIN companies c ON ep.company_id = c.id
        LEFT JOIN sectors sec ON c.sector_id = sec.id
        WHERE sp.start_close > 0
        ORDER BY 6 {order}
        LIMIT :limit
    """), {"end_date": end_date, "lookback_start": lookback_start, "limit": limit}).fetchall()

    return [
        MoverResponse(
            ticker=r[0], name=r[1], sector=r[2], date=str(r[3]),
            close=float(r[4]), pct_change=float(r[5]),
            volume=int(r[6]) if r[6] else None, period=period,
        )
        for r in rows
    ]


# ── Crypto movers ───────────────────────────────────────────

def _get_crypto_movers(db, date, period, order, limit):
    if not date:
        date = _resolve_date(db, "crypto_prices")
        if not date:
            return []

    if period == "daily":
        return _daily_crypto_movers(db, date, order, limit)
    else:
        lookback_start = _compute_lookback_date(date, period)
        return _period_crypto_movers(db, date, lookback_start, period, order, limit)


def _daily_crypto_movers(db, date, order, limit):
    rows = db.execute(text(f"""
        SELECT ca.symbol, ca.name, cp.date::date, cp.close, cp.pct_change, cp.volume_usd
        FROM crypto_prices cp
        JOIN crypto_assets ca ON cp.crypto_id = ca.id
        WHERE cp.date::date = :date AND cp.pct_change IS NOT NULL
        ORDER BY cp.pct_change {order}
        LIMIT :limit
    """), {"date": date, "limit": limit}).fetchall()

    return [
        MoverResponse(
            ticker=r[0], name=r[1], sector="Cryptocurrency", date=str(r[2]),
            close=float(r[3]), pct_change=float(r[4]),
            volume=int(r[5]) if r[5] else None, period="daily",
        )
        for r in rows
    ]


def _period_crypto_movers(db, end_date, lookback_start, period, order, limit):
    rows = db.execute(text(f"""
        WITH end_prices AS (
            SELECT cp.crypto_id, cp.close as end_close, cp.volume_usd
            FROM crypto_prices cp
            WHERE cp.date::date = :end_date AND cp.close IS NOT NULL
        ),
        start_prices AS (
            SELECT DISTINCT ON (cp.crypto_id)
                cp.crypto_id, cp.close as start_close
            FROM crypto_prices cp
            WHERE cp.date::date >= :lookback_start
            AND cp.date::date < :end_date
            AND cp.close IS NOT NULL
            ORDER BY cp.crypto_id, cp.date ASC
        )
        SELECT
            ca.symbol,
            ca.name,
            :end_date as end_date,
            ep.end_close,
            ROUND(((ep.end_close - sp.start_close) / NULLIF(sp.start_close, 0) * 100)::numeric, 2),
            ep.volume_usd
        FROM end_prices ep
        JOIN start_prices sp ON ep.crypto_id = sp.crypto_id
        JOIN crypto_assets ca ON ep.crypto_id = ca.id
        WHERE sp.start_close > 0
        ORDER BY 5 {order}
        LIMIT :limit
    """), {"end_date": end_date, "lookback_start": lookback_start, "limit": limit}).fetchall()

    return [
        MoverResponse(
            ticker=r[0], name=r[1], sector="Cryptocurrency", date=str(r[2]),
            close=float(r[3]), pct_change=float(r[4]),
            volume=int(r[5]) if r[5] else None, period=period,
        )
        for r in rows
    ]
