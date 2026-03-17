"""
Sectors API Routes (Enhanced)

GET /api/sectors              — list all sectors with company counts
GET /api/sectors/{name}       — companies in sector with performance for a date
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel

from backend.api.dependencies import get_db

router = APIRouter(prefix="/api/sectors", tags=["Sectors"])


class SectorSummaryResponse(BaseModel):
    id: int
    name: str
    display_name: str
    company_count: int

class SectorCompanyDetail(BaseModel):
    ticker: str
    name: str
    industry: Optional[str] = None
    close: Optional[float] = None
    pct_change: Optional[float] = None
    volume: Optional[int] = None


@router.get("", response_model=list[SectorSummaryResponse])
def list_sectors(db: Session = Depends(get_db)):
    """List all sectors with the number of companies in each."""
    rows = db.execute(text("""
        SELECT s.id, s.name, s.display_name, COUNT(c.id) as company_count
        FROM sectors s
        LEFT JOIN companies c ON c.sector_id = s.id AND c.is_active = TRUE
        GROUP BY s.id, s.name, s.display_name
        ORDER BY company_count DESC
    """)).fetchall()

    return [
        SectorSummaryResponse(
            id=r[0], name=r[1], display_name=r[2], company_count=r[3],
        )
        for r in rows
    ]


@router.get("/{name}", response_model=list[SectorCompanyDetail])
def get_sector_companies(
    name: str,
    date: Optional[str] = Query(None, description="Date for performance data (YYYY-MM-DD)"),
    sort: str = Query("pct_change", description="Sort by: pct_change, ticker, volume"),
    order: str = Query("desc", description="Sort order: asc or desc"),
    db: Session = Depends(get_db),
):
    """
    Get all companies in a sector with their performance on a given date.

    If no date is provided, uses the latest trading day.
    Supports sorting by pct_change (default), ticker, or volume.
    """
    sector = db.execute(text(
        "SELECT id FROM sectors WHERE name = :name"
    ), {"name": name}).fetchone()

    if not sector:
        raise HTTPException(status_code=404, detail=f"Sector '{name}' not found")

    if not date:
        row = db.execute(text("SELECT MAX(date)::date FROM stocks")).fetchone()
        date = str(row[0]) if row and row[0] else None

    # Validate sort column
    sort_col = {
        "pct_change": "s.pct_change",
        "ticker": "c.ticker",
        "volume": "s.volume",
    }.get(sort, "s.pct_change")

    sort_dir = "DESC" if order.lower() == "desc" else "ASC"
    nulls = "NULLS LAST" if sort_dir == "DESC" else "NULLS FIRST"

    rows = db.execute(text(f"""
        SELECT c.ticker, c.name, c.industry, s.close, s.pct_change, s.volume
        FROM companies c
        LEFT JOIN stocks s ON s.company_id = c.id AND s.date::date = :date
        WHERE c.sector_id = :sector_id AND c.is_active = TRUE
        ORDER BY {sort_col} {sort_dir} {nulls}
    """), {"sector_id": sector[0], "date": date}).fetchall()

    return [
        SectorCompanyDetail(
            ticker=r[0],
            name=r[1],
            industry=r[2],
            close=float(r[3]) if r[3] else None,
            pct_change=float(r[4]) if r[4] else None,
            volume=int(r[5]) if r[5] else None,
        )
        for r in rows
    ]
