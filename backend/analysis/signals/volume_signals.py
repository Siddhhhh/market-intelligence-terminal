"""
Volume Signal Extractor

Detects volume anomalies: spikes, dry-ups, and price-volume divergences.
Uses precomputed volume_ratio from daily_indicators.
"""

from sqlalchemy import text
from sqlalchemy.orm import Session


def extract_volume_signals(db: Session, company_id: int, ticker: str, end_date: str, lookback_days: int = 30) -> list[dict]:
    """Extract volume-based signals."""
    signals = []

    # Get latest volume ratio
    ind = db.execute(text("""
        SELECT volume_ratio FROM daily_indicators
        WHERE company_id = :cid AND date <= :end_date
        ORDER BY date DESC LIMIT 1
    """), {"cid": company_id, "end_date": end_date}).fetchone()

    # Get recent volume and price data
    rows = db.execute(text("""
        SELECT date::date, volume, pct_change, close
        FROM stocks
        WHERE company_id = :cid AND date <= :end_date AND volume IS NOT NULL
        ORDER BY date DESC LIMIT :limit
    """), {"cid": company_id, "end_date": end_date, "limit": lookback_days}).fetchall()

    if len(rows) < 5:
        return signals

    latest_vol = int(rows[0][1]) if rows[0][1] else 0
    latest_pct = float(rows[0][2]) if rows[0][2] else 0
    volumes = [int(r[1]) for r in rows if r[1]]

    if not volumes:
        return signals

    avg_vol = sum(volumes) / len(volumes)
    vol_ratio = float(ind[0]) if ind and ind[0] else (latest_vol / avg_vol if avg_vol > 0 else 1.0)

    # Signal 1: Volume Spike (> 2x average)
    if vol_ratio > 2.0:
        signals.append({
            "factor": "volume_spike",
            "category": "volume",
            "impact": "positive" if latest_pct > 0 else "negative",
            "strength": min((vol_ratio - 1) / 3, 1.0),
            "confidence": 0.80,
        })

    # Signal 2: Volume Dry-Up (< 0.5x average)
    elif vol_ratio < 0.5:
        signals.append({
            "factor": "volume_dryup",
            "category": "volume",
            "impact": "neutral",
            "strength": min((1 - vol_ratio) / 0.5, 1.0),
            "confidence": 0.65,
        })

    # Signal 3: Price-Volume Divergence
    # Price rising but volume declining = weak rally
    recent_prices = [float(r[2]) for r in rows[:5] if r[2] is not None]
    recent_vols = [int(r[1]) for r in rows[:5] if r[1]]

    if len(recent_prices) >= 5 and len(recent_vols) >= 5:
        price_trend = sum(recent_prices[:3]) / 3  # recent avg
        price_older = sum(recent_prices[3:]) / max(len(recent_prices[3:]), 1)
        vol_trend = sum(recent_vols[:3]) / 3
        vol_older = sum(recent_vols[3:]) / max(len(recent_vols[3:]), 1)

        price_up = price_trend > 0
        vol_down = vol_trend < vol_older * 0.8

        if price_up and vol_down:
            signals.append({
                "factor": "price_volume_divergence",
                "category": "volume",
                "impact": "negative",
                "strength": 0.5,
                "confidence": 0.60,
            })

    return signals
