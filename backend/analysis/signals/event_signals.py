"""
Event Signal Extractor

Finds relevant market events (spikes, crashes, sector moves)
that occurred for this ticker or its sector in the lookback window.
"""

from sqlalchemy import text
from sqlalchemy.orm import Session


def extract_event_signals(db: Session, company_id: int, ticker: str, end_date: str, lookback_days: int = 30) -> list[dict]:
    """Extract signals from detected market events."""
    signals = []

    from datetime import datetime, timedelta
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    start_dt = end_dt - timedelta(days=lookback_days + 5)
    start_date = start_dt.strftime("%Y-%m-%d")

    # Direct events for this ticker
    ticker_events = db.execute(text("""
        SELECT event_type, severity, magnitude, date::date, description
        FROM market_events
        WHERE ticker = :ticker
        AND date >= :start_date AND date <= :end_date
        ORDER BY date DESC LIMIT 5
    """), {"ticker": ticker, "start_date": start_date, "end_date": end_date}).fetchall()

    for ev in ticker_events:
        event_type, severity, magnitude, date, desc = ev
        mag = float(magnitude) if magnitude else 0

        impact = "positive" if mag > 0 else "negative" if mag < 0 else "neutral"
        strength = min(abs(mag) / 15, 1.0)
        confidence = {"critical": 0.90, "high": 0.80, "medium": 0.65, "low": 0.50}.get(severity, 0.60)

        signals.append({
            "factor": f"event_{event_type}",
            "category": "event",
            "impact": impact,
            "strength": strength,
            "confidence": confidence,
            "detail": {
                "date": str(date),
                "type": event_type,
                "severity": severity,
                "magnitude": mag,
            },
        })

    # Sector-wide events (market crashes, sector rallies)
    sector_events = db.execute(text("""
        SELECT event_type, severity, magnitude, date::date, description
        FROM market_events
        WHERE event_type IN ('market_crash', 'sector_rally', 'sector_selloff')
        AND date >= :start_date AND date <= :end_date
        ORDER BY date DESC LIMIT 3
    """), {"start_date": start_date, "end_date": end_date}).fetchall()

    for ev in sector_events:
        event_type, severity, magnitude, date, desc = ev
        mag = float(magnitude) if magnitude else 0

        signals.append({
            "factor": f"market_{event_type}",
            "category": "event",
            "impact": "negative" if "crash" in event_type or "selloff" in event_type else "positive",
            "strength": min(abs(mag) / 20, 1.0) if mag else 0.4,
            "confidence": 0.75,
            "detail": {
                "date": str(date),
                "type": event_type,
                "severity": severity,
            },
        })

    return signals


def get_event_context(db: Session, ticker: str, end_date: str, lookback_days: int = 30) -> list[dict]:
    """Get event context for the explanation output."""
    from datetime import datetime, timedelta
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    start_date = (end_dt - timedelta(days=lookback_days + 5)).strftime("%Y-%m-%d")

    events = db.execute(text("""
        SELECT event_type, severity, magnitude, date::date, description
        FROM market_events
        WHERE (ticker = :ticker OR event_type IN ('market_crash', 'sector_rally', 'sector_selloff'))
        AND date >= :start_date AND date <= :end_date
        ORDER BY date DESC LIMIT 10
    """), {"ticker": ticker, "start_date": start_date, "end_date": end_date}).fetchall()

    return [
        {
            "type": r[0], "severity": r[1],
            "magnitude": float(r[2]) if r[2] else None,
            "date": str(r[3]), "description": r[4],
        }
        for r in events
    ]
