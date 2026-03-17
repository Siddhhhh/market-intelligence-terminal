"""
Sector Signal Extractor

Computes stock-vs-sector relative performance.
Detects sector momentum, rotation, and divergence.
"""

from sqlalchemy import text
from sqlalchemy.orm import Session


def extract_sector_signals(db: Session, company_id: int, ticker: str, end_date: str, lookback_days: int = 30) -> list[dict]:
    """Extract sector-relative signals."""
    signals = []

    # Get company's sector
    comp = db.execute(text("""
        SELECT c.sector_id, sec.name, sec.display_name
        FROM companies c
        JOIN sectors sec ON c.sector_id = sec.id
        WHERE c.id = :cid
    """), {"cid": company_id}).fetchone()

    if not comp:
        return signals

    sector_id, sector_name, sector_display = comp

    # Get stock's return over the period
    stock_return = db.execute(text("""
        WITH prices AS (
            SELECT close, ROW_NUMBER() OVER (ORDER BY date DESC) as rn
            FROM stocks WHERE company_id = :cid AND date <= :end_date AND close IS NOT NULL
            ORDER BY date DESC LIMIT :limit
        )
        SELECT
            (SELECT close FROM prices WHERE rn = 1),
            (SELECT close FROM prices WHERE rn = :limit)
    """), {"cid": company_id, "end_date": end_date, "limit": lookback_days}).fetchone()

    if not stock_return or not stock_return[0] or not stock_return[1] or float(stock_return[1]) <= 0:
        return signals

    stock_ret = ((float(stock_return[0]) - float(stock_return[1])) / float(stock_return[1])) * 100

    # Get sector average return over same period
    from datetime import datetime, timedelta
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    sector_start = (end_dt - timedelta(days=45)).strftime("%Y-%m-%d")

    sector_avg = db.execute(text("""
        SELECT AVG(sp.avg_pct_change) as avg_daily
        FROM sector_performance sp
        WHERE sp.sector_id = :sid
        AND sp.date <= :end_date
        AND sp.date >= :sector_start
    """), {"sid": sector_id, "end_date": end_date, "sector_start": sector_start}).fetchone()

    sector_daily_avg = float(sector_avg[0]) if sector_avg and sector_avg[0] else 0
    sector_period_return = sector_daily_avg * lookback_days

    relative_strength = stock_ret - sector_period_return

    # Signal 1: Outperforming Sector
    if relative_strength > 2:
        signals.append({
            "factor": "sector_outperformance",
            "category": "sector",
            "impact": "positive",
            "strength": min(relative_strength / 15, 1.0),
            "confidence": 0.75,
        })
    elif relative_strength < -2:
        signals.append({
            "factor": "sector_underperformance",
            "category": "sector",
            "impact": "negative",
            "strength": min(abs(relative_strength) / 15, 1.0),
            "confidence": 0.75,
        })

    # Signal 2: Sector Momentum (is the sector itself moving?)
    if abs(sector_period_return) > 3:
        signals.append({
            "factor": "sector_momentum",
            "category": "sector",
            "impact": "positive" if sector_period_return > 0 else "negative",
            "strength": min(abs(sector_period_return) / 10, 1.0),
            "confidence": 0.80,
        })

    # Signal 3: Sector Divergence (stock going opposite to sector)
    if (stock_ret > 2 and sector_period_return < -2) or (stock_ret < -2 and sector_period_return > 2):
        signals.append({
            "factor": "sector_divergence",
            "category": "sector",
            "impact": "neutral",
            "strength": min(abs(stock_ret - sector_period_return) / 10, 1.0),
            "confidence": 0.65,
        })

    return signals
