"""
Sector Heatmap API Routes (Optimized)

GET /api/heatmap           — sector performance for a given date
GET /api/heatmap/history   — sector performance over a date range

Uses precomputed sector_performance table for instant responses.
Falls back to live computation if precomputed data isn't available.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel

from backend.api.dependencies import get_db

router = APIRouter(prefix="/api/heatmap", tags=["Heatmap"])


class SectorHeatmapEntry(BaseModel):
    sector: str
    display_name: str
    avg_pct_change: float
    company_count: int
    total_volume: Optional[int] = None
    top_gainer: Optional[str] = None
    top_gainer_pct: Optional[float] = None
    top_loser: Optional[str] = None
    top_loser_pct: Optional[float] = None


class SectorHistoryEntry(BaseModel):
    date: str
    sector: str
    display_name: str
    avg_pct_change: float
    company_count: int


@router.get("", response_model=list[SectorHeatmapEntry])
def sector_heatmap(
    date: Optional[str] = Query(None, description="Date (YYYY-MM-DD), defaults to latest trading day"),
    db: Session = Depends(get_db),
):
    """
    Get sector performance heatmap data for a given date.

    Uses precomputed sector_performance table for instant response (~5ms).
    Falls back to live aggregation if precomputed data isn't available.
    """
    if not date:
        row = db.execute(text("SELECT MAX(date)::date FROM stocks")).fetchone()
        date = str(row[0]) if row and row[0] else None
        if not date:
            return []

    # Try precomputed table first (fast path: ~5ms)
    precomputed = db.execute(text("""
        SELECT
            sec.name,
            sec.display_name,
            sp.avg_pct_change,
            sp.company_count,
            sp.total_volume,
            sp.top_gainer_ticker,
            sp.top_gainer_pct,
            sp.top_loser_ticker,
            sp.top_loser_pct
        FROM sector_performance sp
        JOIN sectors sec ON sp.sector_id = sec.id
        WHERE sp.date = :date
        ORDER BY sp.avg_pct_change DESC
    """), {"date": date}).fetchall()

    if precomputed:
        return [
            SectorHeatmapEntry(
                sector=r[0],
                display_name=r[1],
                avg_pct_change=float(r[2]) if r[2] else 0.0,
                company_count=r[3],
                total_volume=int(r[4]) if r[4] else None,
                top_gainer=r[5],
                top_gainer_pct=float(r[6]) if r[6] else None,
                top_loser=r[7],
                top_loser_pct=float(r[8]) if r[8] else None,
            )
            for r in precomputed
        ]

    # Fallback: live computation (slower, ~200ms)
    return _compute_live(db, date)


@router.get("/history", response_model=list[SectorHistoryEntry])
def sector_heatmap_history(
    sector: Optional[str] = Query(None, description="Filter by sector name"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """
    Get sector performance history over a date range.

    Useful for sector rotation analysis and historical comparison.
    """
    query = """
        SELECT sp.date, sec.name, sec.display_name, sp.avg_pct_change, sp.company_count
        FROM sector_performance sp
        JOIN sectors sec ON sp.sector_id = sec.id
        WHERE 1=1
    """
    params: dict = {}

    if sector:
        query += " AND sec.name = :sector"
        params["sector"] = sector

    if start_date:
        query += " AND sp.date >= :start_date"
        params["start_date"] = start_date

    if end_date:
        query += " AND sp.date <= :end_date"
        params["end_date"] = end_date

    query += " ORDER BY sp.date DESC LIMIT :limit"
    params["limit"] = limit

    rows = db.execute(text(query), params).fetchall()

    return [
        SectorHistoryEntry(
            date=str(r[0]),
            sector=r[1],
            display_name=r[2],
            avg_pct_change=float(r[3]) if r[3] else 0.0,
            company_count=r[4],
        )
        for r in rows
    ]


def _compute_live(db: Session, date: str) -> list[SectorHeatmapEntry]:
    """
    Fallback: live computation using a single optimized SQL query.
    No N+1 queries — uses window functions for gainer/loser in one pass.
    """
    rows = db.execute(text("""
        WITH sector_data AS (
            SELECT
                sec.name as sector_name,
                sec.display_name,
                c.ticker,
                s.pct_change,
                s.volume,
                ROW_NUMBER() OVER (PARTITION BY sec.id ORDER BY s.pct_change DESC) as gain_rank,
                ROW_NUMBER() OVER (PARTITION BY sec.id ORDER BY s.pct_change ASC) as loss_rank
            FROM stocks s
            JOIN companies c ON s.company_id = c.id
            JOIN sectors sec ON c.sector_id = sec.id
            WHERE s.date::date = :date AND s.pct_change IS NOT NULL
        )
        SELECT
            sector_name,
            display_name,
            ROUND(AVG(pct_change)::numeric, 4) as avg_pct,
            COUNT(*) as company_count,
            SUM(volume) as total_vol,
            MAX(CASE WHEN gain_rank = 1 THEN ticker END) as top_gainer,
            MAX(CASE WHEN gain_rank = 1 THEN pct_change END) as top_gainer_pct,
            MAX(CASE WHEN loss_rank = 1 THEN ticker END) as top_loser,
            MAX(CASE WHEN loss_rank = 1 THEN pct_change END) as top_loser_pct
        FROM sector_data
        GROUP BY sector_name, display_name
        ORDER BY avg_pct DESC
    """), {"date": date}).fetchall()

    return [
        SectorHeatmapEntry(
            sector=r[0],
            display_name=r[1],
            avg_pct_change=float(r[2]) if r[2] else 0.0,
            company_count=r[3],
            total_volume=int(r[4]) if r[4] else None,
            top_gainer=r[5],
            top_gainer_pct=float(r[6]) if r[6] else None,
            top_loser=r[7],
            top_loser_pct=float(r[8]) if r[8] else None,
        )
        for r in rows
    ]
