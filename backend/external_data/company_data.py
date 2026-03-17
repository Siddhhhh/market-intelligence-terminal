"""
Company Data Provider

Wraps yfinance so core logic never calls it directly.
Caches results in company_cache table.
Falls back gracefully if yfinance is unavailable.
"""

import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text
from sqlalchemy.orm import Session
from loguru import logger


CACHE_TTL_HOURS = 12


def get_company_data(db: Session, ticker: str) -> dict:
    """
    Get company fundamental data.
    Checks DB cache first, fetches from yfinance if stale or missing.
    """
    ticker = ticker.upper()

    # Check cache
    cached = _get_cached(db, ticker)
    if cached:
        return cached

    # Fetch from yfinance
    fresh = _fetch_from_yfinance(ticker)
    if fresh:
        _store_cache(db, ticker, fresh)
        return fresh

    # Fallback: return empty structure
    return {
        "ticker": ticker,
        "market_cap": None,
        "pe_ratio": None,
        "forward_pe": None,
        "revenue": None,
        "net_income": None,
        "profit_margin": None,
        "eps": None,
        "revenue_growth": None,
        "fifty_two_week_high": None,
        "fifty_two_week_low": None,
        "avg_volume": None,
        "top_holders": [],
    }


def _get_cached(db: Session, ticker: str) -> dict | None:
    """Check if a fresh cached result exists."""
    try:
        row = db.execute(text("""
            SELECT market_cap, pe_ratio, forward_pe, revenue, net_income,
                   profit_margin, eps, revenue_growth, fifty_two_week_high,
                   fifty_two_week_low, avg_volume, top_holders, updated_at
            FROM company_cache
            WHERE ticker = :ticker
        """), {"ticker": ticker}).fetchone()

        if row and row[12]:
            age = (datetime.now() - row[12]).total_seconds()
            if age < CACHE_TTL_HOURS * 3600:
                return {
                    "ticker": ticker,
                    "market_cap": int(row[0]) if row[0] else None,
                    "pe_ratio": float(row[1]) if row[1] else None,
                    "forward_pe": float(row[2]) if row[2] else None,
                    "revenue": int(row[3]) if row[3] else None,
                    "net_income": int(row[4]) if row[4] else None,
                    "profit_margin": float(row[5]) if row[5] else None,
                    "eps": float(row[6]) if row[6] else None,
                    "revenue_growth": float(row[7]) if row[7] else None,
                    "fifty_two_week_high": float(row[8]) if row[8] else None,
                    "fifty_two_week_low": float(row[9]) if row[9] else None,
                    "avg_volume": int(row[10]) if row[10] else None,
                    "top_holders": row[11] if row[11] else [],
                }
    except Exception as e:
        logger.warning(f"Cache read failed for {ticker}: {e}")

    return None


def _fetch_from_yfinance(ticker: str) -> dict | None:
    """Fetch company data from yfinance."""
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        info = stock.info

        if not info or info.get("regularMarketPrice") is None:
            return None

        # Get institutional holders
        holders = []
        try:
            inst_holders = stock.institutional_holders
            if inst_holders is not None and not inst_holders.empty:
                for _, row in inst_holders.head(10).iterrows():
                    holders.append({
                        "name": str(row.get("Holder", "")),
                        "shares": int(row.get("Shares", 0)) if row.get("Shares") else 0,
                        "pct": float(row.get("% Out", 0)) if row.get("% Out") else 0,
                    })
        except Exception:
            pass

        return {
            "ticker": ticker,
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "revenue": info.get("totalRevenue"),
            "net_income": info.get("netIncomeToCommon"),
            "profit_margin": info.get("profitMargins"),
            "eps": info.get("trailingEps"),
            "revenue_growth": info.get("revenueGrowth"),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
            "avg_volume": info.get("averageVolume"),
            "top_holders": holders,
        }

    except Exception as e:
        logger.error(f"yfinance fetch failed for {ticker}: {e}")
        return None


def _store_cache(db: Session, ticker: str, data: dict) -> None:
    """Store or update company cache."""
    try:
        import json
        db.execute(text("""
            INSERT INTO company_cache
                (ticker, market_cap, pe_ratio, forward_pe, revenue, net_income,
                 profit_margin, eps, revenue_growth, fifty_two_week_high,
                 fifty_two_week_low, avg_volume, top_holders, updated_at)
            VALUES
                (:ticker, :market_cap, :pe_ratio, :forward_pe, :revenue, :net_income,
                 :profit_margin, :eps, :revenue_growth, :fifty_two_week_high,
                 :fifty_two_week_low, :avg_volume, :top_holders, NOW())
            ON CONFLICT (ticker) DO UPDATE SET
                market_cap = EXCLUDED.market_cap,
                pe_ratio = EXCLUDED.pe_ratio,
                forward_pe = EXCLUDED.forward_pe,
                revenue = EXCLUDED.revenue,
                net_income = EXCLUDED.net_income,
                profit_margin = EXCLUDED.profit_margin,
                eps = EXCLUDED.eps,
                revenue_growth = EXCLUDED.revenue_growth,
                fifty_two_week_high = EXCLUDED.fifty_two_week_high,
                fifty_two_week_low = EXCLUDED.fifty_two_week_low,
                avg_volume = EXCLUDED.avg_volume,
                top_holders = EXCLUDED.top_holders,
                updated_at = NOW()
        """), {
            "ticker": ticker,
            "market_cap": data.get("market_cap"),
            "pe_ratio": data.get("pe_ratio"),
            "forward_pe": data.get("forward_pe"),
            "revenue": data.get("revenue"),
            "net_income": data.get("net_income"),
            "profit_margin": data.get("profit_margin"),
            "eps": data.get("eps"),
            "revenue_growth": data.get("revenue_growth"),
            "fifty_two_week_high": data.get("fifty_two_week_high"),
            "fifty_two_week_low": data.get("fifty_two_week_low"),
            "avg_volume": data.get("avg_volume"),
            "top_holders": json.dumps(data.get("top_holders", [])),
        })
        db.commit()
    except Exception as e:
        logger.warning(f"Cache store failed for {ticker}: {e}")
