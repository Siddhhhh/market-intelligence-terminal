"""
Comparison API Routes

GET /api/compare/stock    — compare a stock across two time periods
GET /api/compare/sector   — compare sectors across two time periods
GET /api/compare/crypto   — compare a crypto asset across two time periods
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.api.dependencies import get_db
from backend.analysis.comparison_engine import compare_stock, compare_sectors, compare_crypto

router = APIRouter(prefix="/api/compare", tags=["Comparison"])


class PeriodMetrics(BaseModel):
    label: Optional[str] = None
    trading_days: int = 0
    total_return: Optional[float] = None
    avg_daily_change: Optional[float] = None
    volatility: Optional[float] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    avg_volume: Optional[int] = None
    best_day: Optional[dict] = None
    worst_day: Optional[dict] = None

class DiffMetrics(BaseModel):
    return_diff: float = 0
    volatility_diff: float = 0
    primary_outperformed: bool = False
    direction: str = "equal"

class StockCompareResponse(BaseModel):
    ticker: str
    name: str
    primary: PeriodMetrics
    comparison: PeriodMetrics
    diff: DiffMetrics

class SectorCompareResponse(BaseModel):
    primary_label: str
    comparison_label: str
    primary_sectors: dict
    comparison_sectors: dict
    diffs: dict

class CryptoCompareResponse(BaseModel):
    symbol: str
    name: str
    primary: PeriodMetrics
    comparison: PeriodMetrics
    diff: DiffMetrics


@router.get("/stock", response_model=StockCompareResponse)
def compare_stock_endpoint(
    ticker: str = Query(..., description="Stock ticker (e.g., AAPL)"),
    p1_start: str = Query(..., description="Primary period start (YYYY-MM-DD)"),
    p1_end: str = Query(..., description="Primary period end (YYYY-MM-DD)"),
    p2_start: str = Query(..., description="Comparison period start (YYYY-MM-DD)"),
    p2_end: str = Query(..., description="Comparison period end (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    """
    Compare a stock's performance across two time periods.

    Example: AAPL in 2008 vs 2023
        /api/compare/stock?ticker=AAPL&p1_start=2008-01-01&p1_end=2008-12-31&p2_start=2023-01-01&p2_end=2023-12-31
    """
    result = compare_stock(db, ticker, p1_start, p1_end, p2_start, p2_end)

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result


@router.get("/sector", response_model=SectorCompareResponse)
def compare_sector_endpoint(
    p1_start: str = Query(..., description="Primary period start"),
    p1_end: str = Query(..., description="Primary period end"),
    p2_start: str = Query(..., description="Comparison period start"),
    p2_end: str = Query(..., description="Comparison period end"),
    sector: Optional[str] = Query(None, description="Specific sector (e.g., technology)"),
    db: Session = Depends(get_db),
):
    """
    Compare sector performance across two time periods.

    Example: Sectors pre vs post COVID
        /api/compare/sector?p1_start=2019-01-01&p1_end=2019-12-31&p2_start=2021-01-01&p2_end=2021-12-31
    """
    return compare_sectors(db, p1_start, p1_end, p2_start, p2_end, sector)


@router.get("/crypto", response_model=CryptoCompareResponse)
def compare_crypto_endpoint(
    symbol: str = Query(..., description="Crypto symbol (BTC, ETH, SOL)"),
    p1_start: str = Query(..., description="Primary period start"),
    p1_end: str = Query(..., description="Primary period end"),
    p2_start: str = Query(..., description="Comparison period start"),
    p2_end: str = Query(..., description="Comparison period end"),
    db: Session = Depends(get_db),
):
    """
    Compare a crypto asset across two time periods.

    Example: BTC 2021 vs 2024
        /api/compare/crypto?symbol=BTC&p1_start=2021-01-01&p1_end=2021-12-31&p2_start=2024-01-01&p2_end=2024-12-31
    """
    result = compare_crypto(db, symbol, p1_start, p1_end, p2_start, p2_end)

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result
