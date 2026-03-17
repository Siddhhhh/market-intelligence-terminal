"""
Crypto API Routes

GET /api/crypto          — list crypto assets
GET /api/crypto/{symbol} — price history for a crypto asset
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel

from backend.api.dependencies import get_db

router = APIRouter(prefix="/api/crypto", tags=["Crypto"])


class CryptoAssetResponse(BaseModel):
    id: int
    symbol: str
    name: str
    is_active: bool

class CryptoPriceResponse(BaseModel):
    date: str
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: float
    volume_usd: Optional[float] = None
    pct_change: Optional[float] = None

class CryptoHistoryResponse(BaseModel):
    symbol: str
    name: str
    total_records: int
    data: list[CryptoPriceResponse]


@router.get("", response_model=list[CryptoAssetResponse])
def list_crypto_assets(db: Session = Depends(get_db)):
    """List all crypto assets."""
    rows = db.execute(text(
        "SELECT id, symbol, name, is_active FROM crypto_assets ORDER BY symbol"
    )).fetchall()

    return [
        CryptoAssetResponse(id=r[0], symbol=r[1], name=r[2], is_active=r[3])
        for r in rows
    ]


@router.get("/{symbol}", response_model=CryptoHistoryResponse)
def get_crypto_history(
    symbol: str,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(1000, ge=1, le=10000),
    db: Session = Depends(get_db),
):
    """Get price history for a crypto asset (BTC, ETH, SOL)."""
    symbol = symbol.upper()

    asset = db.execute(text(
        "SELECT id, symbol, name FROM crypto_assets WHERE symbol = :symbol"
    ), {"symbol": symbol}).fetchone()

    if not asset:
        raise HTTPException(status_code=404, detail=f"Crypto asset '{symbol}' not found")

    query = """
        SELECT date::date, open, high, low, close, volume_usd, pct_change
        FROM crypto_prices
        WHERE crypto_id = :crypto_id
    """
    params: dict = {"crypto_id": asset[0]}

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
        CryptoPriceResponse(
            date=str(r[0]),
            open=float(r[1]) if r[1] else None,
            high=float(r[2]) if r[2] else None,
            low=float(r[3]) if r[3] else None,
            close=float(r[4]),
            volume_usd=float(r[5]) if r[5] else None,
            pct_change=float(r[6]) if r[6] else None,
        )
        for r in rows
    ]

    return CryptoHistoryResponse(
        symbol=asset[1], name=asset[2],
        total_records=len(data), data=data,
    )
