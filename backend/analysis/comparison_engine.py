"""
Comparison Engine — Cross-Period Financial Analysis

Computes performance metrics over two date ranges and returns
structured comparison data for stocks, sectors, and crypto.

All computations use SQL aggregation — no Python loops over rows.

Usage:
    from backend.analysis.comparison_engine import compare_stock, compare_sectors, compare_crypto
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text
from sqlalchemy.orm import Session
from loguru import logger


def compare_stock(
    db: Session,
    ticker: str,
    p1_start: str, p1_end: str,
    p2_start: str, p2_end: str,
) -> dict:
    """
    Compare a stock's performance across two time periods.

    Returns: period return, avg daily change, volatility, best/worst days,
    avg volume, and the diff between periods.
    """
    company = db.execute(text(
        "SELECT id, ticker, name FROM companies WHERE ticker = :ticker"
    ), {"ticker": ticker.upper()}).fetchone()

    if not company:
        return {"error": f"Ticker '{ticker}' not found"}

    p1 = _stock_period_metrics(db, company[0], p1_start, p1_end)
    p2 = _stock_period_metrics(db, company[0], p2_start, p2_end)

    p1["label"] = f"{p1_start} to {p1_end}"
    p2["label"] = f"{p2_start} to {p2_end}"

    return {
        "ticker": company[1],
        "name": company[2],
        "primary": p1,
        "comparison": p2,
        "diff": _compute_diff(p1, p2),
    }


def compare_sectors(
    db: Session,
    p1_start: str, p1_end: str,
    p2_start: str, p2_end: str,
    sector: str = None,
) -> dict:
    """
    Compare sector performance across two time periods.
    If sector is specified, compares that sector only.
    Otherwise compares all sectors.
    """
    p1 = _sector_period_metrics(db, p1_start, p1_end, sector)
    p2 = _sector_period_metrics(db, p2_start, p2_end, sector)

    # Compute diffs per sector
    diffs = {}
    for name in set(list(p1.keys()) + list(p2.keys())):
        s1 = p1.get(name, {})
        s2 = p2.get(name, {})
        r1 = s1.get("total_return", 0) or 0
        r2 = s2.get("total_return", 0) or 0
        diffs[name] = {
            "return_diff": round(r1 - r2, 2),
            "primary_return": r1,
            "comparison_return": r2,
            "direction": "improved" if r1 > r2 else "declined" if r1 < r2 else "unchanged",
        }

    return {
        "primary_label": f"{p1_start} to {p1_end}",
        "comparison_label": f"{p2_start} to {p2_end}",
        "primary_sectors": p1,
        "comparison_sectors": p2,
        "diffs": diffs,
    }


def compare_crypto(
    db: Session,
    symbol: str,
    p1_start: str, p1_end: str,
    p2_start: str, p2_end: str,
) -> dict:
    """Compare a crypto asset across two time periods."""
    asset = db.execute(text(
        "SELECT id, symbol, name FROM crypto_assets WHERE symbol = :symbol"
    ), {"symbol": symbol.upper()}).fetchone()

    if not asset:
        return {"error": f"Crypto '{symbol}' not found"}

    p1 = _crypto_period_metrics(db, asset[0], p1_start, p1_end)
    p2 = _crypto_period_metrics(db, asset[0], p2_start, p2_end)

    p1["label"] = f"{p1_start} to {p1_end}"
    p2["label"] = f"{p2_start} to {p2_end}"

    return {
        "symbol": asset[1],
        "name": asset[2],
        "primary": p1,
        "comparison": p2,
        "diff": _compute_diff(p1, p2),
    }


# ── Internal helpers ────────────────────────────────────────

def _stock_period_metrics(db: Session, company_id: int, start: str, end: str) -> dict:
    """Compute stock metrics for a single period using one SQL query."""
    row = db.execute(text("""
        SELECT
            COUNT(*) as trading_days,
            ROUND(AVG(pct_change)::numeric, 4) as avg_daily_change,
            ROUND(STDDEV(pct_change)::numeric, 4) as volatility,
            MIN(close) as min_price,
            MAX(close) as max_price,
            ROUND(AVG(volume)::numeric, 0) as avg_volume
        FROM stocks
        WHERE company_id = :cid
        AND date >= :start_date AND date <= :end_date
        AND pct_change IS NOT NULL
    """), {"cid": company_id, "start_date": start, "end_date": end}).fetchone()

    # Period return: first close to last close
    first_last = db.execute(text("""
        SELECT
            (SELECT close FROM stocks WHERE company_id = :cid AND date >= :start_date AND date <= :end_date ORDER BY date ASC LIMIT 1),
            (SELECT close FROM stocks WHERE company_id = :cid AND date >= :start_date AND date <= :end_date ORDER BY date DESC LIMIT 1)
    """), {"cid": company_id, "start_date": start, "end_date": end}).fetchone()

    total_return = None
    if first_last and first_last[0] and first_last[1] and float(first_last[0]) > 0:
        total_return = round(((float(first_last[1]) - float(first_last[0])) / float(first_last[0])) * 100, 2)

    # Best and worst days
    best = db.execute(text("""
        SELECT date::date, pct_change FROM stocks
        WHERE company_id = :cid AND date >= :start_date AND date <= :end_date AND pct_change IS NOT NULL
        ORDER BY pct_change DESC LIMIT 1
    """), {"cid": company_id, "start_date": start, "end_date": end}).fetchone()

    worst = db.execute(text("""
        SELECT date::date, pct_change FROM stocks
        WHERE company_id = :cid AND date >= :start_date AND date <= :end_date AND pct_change IS NOT NULL
        ORDER BY pct_change ASC LIMIT 1
    """), {"cid": company_id, "start_date": start, "end_date": end}).fetchone()

    return {
        "trading_days": row[0] if row else 0,
        "total_return": total_return,
        "avg_daily_change": float(row[1]) if row and row[1] else None,
        "volatility": float(row[2]) if row and row[2] else None,
        "min_price": float(row[3]) if row and row[3] else None,
        "max_price": float(row[4]) if row and row[4] else None,
        "avg_volume": int(row[5]) if row and row[5] else None,
        "best_day": {"date": str(best[0]), "pct": float(best[1])} if best else None,
        "worst_day": {"date": str(worst[0]), "pct": float(worst[1])} if worst else None,
    }


def _sector_period_metrics(db: Session, start: str, end: str, sector: str = None) -> dict:
    """Compute sector-level metrics for a period."""
    query = """
        SELECT
            sec.name,
            sec.display_name,
            COUNT(DISTINCT c.id) as companies,
            ROUND(AVG(s.pct_change)::numeric, 4) as avg_daily,
            ROUND(STDDEV(s.pct_change)::numeric, 4) as volatility
        FROM stocks s
        JOIN companies c ON s.company_id = c.id
        JOIN sectors sec ON c.sector_id = sec.id
        WHERE s.date >= :start_date AND s.date <= :end_date
        AND s.pct_change IS NOT NULL
    """
    params = {"start_date": start, "end_date": end}

    if sector:
        query += " AND sec.name = :sector"
        params["sector"] = sector

    query += " GROUP BY sec.name, sec.display_name ORDER BY avg_daily DESC"

    rows = db.execute(text(query), params).fetchall()

    result = {}
    for r in rows:
        # Approximate total return from avg daily * trading days
        trading_days = db.execute(text("""
            SELECT COUNT(DISTINCT date::date) FROM stocks
            WHERE date >= :start_date AND date <= :end_date
        """), {"start_date": start, "end_date": end}).scalar() or 0

        approx_return = round(float(r[3]) * trading_days, 2) if r[3] else 0

        result[r[0]] = {
            "display_name": r[1],
            "companies": r[2],
            "avg_daily_change": float(r[3]) if r[3] else 0,
            "volatility": float(r[4]) if r[4] else 0,
            "total_return": approx_return,
            "trading_days": trading_days,
        }

    return result


def _crypto_period_metrics(db: Session, crypto_id: int, start: str, end: str) -> dict:
    """Compute crypto metrics for a single period."""
    row = db.execute(text("""
        SELECT
            COUNT(*) as days,
            ROUND(AVG(pct_change)::numeric, 4) as avg_daily,
            ROUND(STDDEV(pct_change)::numeric, 4) as volatility,
            MIN(close) as min_price,
            MAX(close) as max_price
        FROM crypto_prices
        WHERE crypto_id = :cid
        AND date >= :start_date AND date <= :end_date
        AND pct_change IS NOT NULL
    """), {"cid": crypto_id, "start_date": start, "end_date": end}).fetchone()

    first_last = db.execute(text("""
        SELECT
            (SELECT close FROM crypto_prices WHERE crypto_id = :cid AND date >= :start_date AND date <= :end_date ORDER BY date ASC LIMIT 1),
            (SELECT close FROM crypto_prices WHERE crypto_id = :cid AND date >= :start_date AND date <= :end_date ORDER BY date DESC LIMIT 1)
    """), {"cid": crypto_id, "start_date": start, "end_date": end}).fetchone()

    total_return = None
    if first_last and first_last[0] and first_last[1] and float(first_last[0]) > 0:
        total_return = round(((float(first_last[1]) - float(first_last[0])) / float(first_last[0])) * 100, 2)

    return {
        "trading_days": row[0] if row else 0,
        "total_return": total_return,
        "avg_daily_change": float(row[1]) if row and row[1] else None,
        "volatility": float(row[2]) if row and row[2] else None,
        "min_price": float(row[3]) if row and row[3] else None,
        "max_price": float(row[4]) if row and row[4] else None,
    }


def _compute_diff(p1: dict, p2: dict) -> dict:
    """Compute the difference between two period metrics."""
    r1 = p1.get("total_return") or 0
    r2 = p2.get("total_return") or 0
    v1 = p1.get("volatility") or 0
    v2 = p2.get("volatility") or 0

    return {
        "return_diff": round(r1 - r2, 2),
        "volatility_diff": round(v1 - v2, 4),
        "primary_outperformed": r1 > r2,
        "direction": "primary_better" if r1 > r2 else "comparison_better" if r2 > r1 else "equal",
    }
