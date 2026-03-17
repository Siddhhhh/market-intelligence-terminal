"""
Company Intelligence API Routes

GET /api/company/{ticker}/intelligence       — company info + indicators + holders
GET /api/company/{ticker}/movement-explanation — movement attribution with scored drivers
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.api.dependencies import get_db
from backend.external_data.company_data import get_company_data
from backend.analysis.movement_engine import explain_movement
from backend.analysis.presentation_mapper import map_all_drivers, generate_narrative_summary

router = APIRouter(prefix="/api/company", tags=["Company Intelligence"])


@router.get("/{ticker}/intelligence")
def company_intelligence(
    ticker: str,
    db: Session = Depends(get_db),
):
    """
    Full company intelligence package.

    Returns: company info, financials, technical indicators,
    institutional holders, sector context, and relationships.
    """
    ticker = ticker.upper()

    # Basic company info from DB
    company = db.execute(text("""
        SELECT c.id, c.ticker, c.name, sec.name, sec.display_name, c.industry
        FROM companies c
        LEFT JOIN sectors sec ON c.sector_id = sec.id
        WHERE c.ticker = :ticker
    """), {"ticker": ticker}).fetchone()

    if not company:
        raise HTTPException(status_code=404, detail=f"Ticker '{ticker}' not found")

    company_id = company[0]

    # Fundamentals from provider (cached)
    fundamentals = get_company_data(db, ticker)

    # Latest indicators
    ind = db.execute(text("""
        SELECT date::date, ma20, ma50, ma200, rsi, macd, macd_signal,
               macd_histogram, volatility_20d, volume_ratio, trend_direction
        FROM daily_indicators
        WHERE company_id = :cid
        ORDER BY date DESC LIMIT 1
    """), {"cid": company_id}).fetchone()

    indicators = {}
    if ind:
        indicators = {
            "date": str(ind[0]),
            "ma20": float(ind[1]) if ind[1] else None,
            "ma50": float(ind[2]) if ind[2] else None,
            "ma200": float(ind[3]) if ind[3] else None,
            "rsi": float(ind[4]) if ind[4] else None,
            "macd": float(ind[5]) if ind[5] else None,
            "macd_signal": float(ind[6]) if ind[6] else None,
            "macd_histogram": float(ind[7]) if ind[7] else None,
            "volatility_20d": float(ind[8]) if ind[8] else None,
            "volume_ratio": float(ind[9]) if ind[9] else None,
            "trend": ind[10] or "unknown",
        }

    # Latest price
    latest = db.execute(text("""
        SELECT date::date, close, pct_change, volume
        FROM stocks WHERE company_id = :cid
        ORDER BY date DESC LIMIT 1
    """), {"cid": company_id}).fetchone()

    market = {}
    if latest:
        market = {
            "date": str(latest[0]),
            "close": float(latest[1]) if latest[1] else None,
            "pct_change": float(latest[2]) if latest[2] else None,
            "volume": int(latest[3]) if latest[3] else None,
        }

    # Relationships
    relationships = db.execute(text("""
        SELECT c2.ticker, c2.name, cr.relationship_type, cr.confidence_score, cr.description
        FROM company_relationships cr
        JOIN companies c2 ON cr.related_company_id = c2.id
        WHERE cr.company_id = :cid
        ORDER BY cr.confidence_score DESC LIMIT 10
    """), {"cid": company_id}).fetchall()

    rels = [
        {
            "ticker": r[0], "name": r[1], "type": r[2],
            "confidence": float(r[3]) if r[3] else None,
            "description": r[4],
        }
        for r in relationships
    ]

    return {
        "ticker": ticker,
        "name": company[2],
        "sector": company[4],
        "industry": company[5],
        "market": market,
        "financials": {
            "market_cap": fundamentals.get("market_cap"),
            "pe_ratio": fundamentals.get("pe_ratio"),
            "forward_pe": fundamentals.get("forward_pe"),
            "revenue": fundamentals.get("revenue"),
            "net_income": fundamentals.get("net_income"),
            "profit_margin": fundamentals.get("profit_margin"),
            "eps": fundamentals.get("eps"),
            "revenue_growth": fundamentals.get("revenue_growth"),
        },
        "indicators": indicators,
        "holders": fundamentals.get("top_holders", []),
        "relationships": rels,
    }


@router.get("/{ticker}/movement-explanation")
def movement_explanation(
    ticker: str,
    range: str = Query("7d", description="Lookback period: 1d, 7d, 14d, 30d, 90d"),
    db: Session = Depends(get_db),
):
    """
    Movement Attribution Engine output.

    Returns structured, deterministic explanation of why the stock moved.
    Includes scored drivers, technical context, macro context, events,
    buy/sell zones, and confidence metrics.
    """
    valid_ranges = ["1d", "7d", "14d", "30d", "90d"]
    if range not in valid_ranges:
        raise HTTPException(status_code=400, detail=f"Invalid range. Use: {valid_ranges}")

    result = explain_movement(db, ticker, range)

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    # Apply presentation mapping to drivers
    result["drivers"] = map_all_drivers(result.get("drivers", []))

    # Generate narrative summary
    result["narrative"] = generate_narrative_summary(
        result.get("ticker", ticker),
        result.get("period_return", 0),
        range,
        result["drivers"],
    )

    return result
