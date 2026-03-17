"""
Macro Signal Extractor

Detects macroeconomic shifts that could impact stock movement:
interest rate changes, VIX spikes, CPI surprises.
Forward-fills macro data to align with trading dates.
"""

from sqlalchemy import text
from sqlalchemy.orm import Session


def extract_macro_signals(db: Session, company_id: int, ticker: str, end_date: str, lookback_days: int = 30) -> list[dict]:
    """Extract macro-economic signals."""
    signals = []

    # Get latest macro values
    macro_data = {}
    for indicator in ["fed_funds_rate", "vix", "cpi", "unemployment_rate"]:
        row = db.execute(text("""
            SELECT value, change_pct, date::date
            FROM macro_events
            WHERE indicator = :ind AND date <= :end_date
            ORDER BY date DESC LIMIT 1
        """), {"ind": indicator, "end_date": end_date}).fetchone()

        if row:
            macro_data[indicator] = {
                "value": float(row[0]) if row[0] else None,
                "change_pct": float(row[1]) if row[1] else None,
                "date": str(row[2]),
                "stale": _is_stale(str(row[2]), end_date, indicator),
            }

    # Signal 1: Interest Rate Environment
    fed = macro_data.get("fed_funds_rate")
    if fed and fed["value"] is not None:
        rate = fed["value"]
        if rate > 4.5:
            signals.append({
                "factor": "high_interest_rate_environment",
                "category": "macro",
                "impact": "negative",
                "strength": min((rate - 3) / 5, 1.0),
                "confidence": 0.70 if not fed["stale"] else 0.50,
            })
        elif rate < 1.5:
            signals.append({
                "factor": "low_interest_rate_environment",
                "category": "macro",
                "impact": "positive",
                "strength": min((2 - rate) / 2, 1.0),
                "confidence": 0.70 if not fed["stale"] else 0.50,
            })

    # Signal 2: VIX (Market Fear)
    vix = macro_data.get("vix")
    if vix and vix["value"] is not None:
        vix_val = vix["value"]
        if vix_val > 25:
            signals.append({
                "factor": "elevated_market_fear",
                "category": "macro",
                "impact": "negative",
                "strength": min((vix_val - 15) / 30, 1.0),
                "confidence": 0.80 if not vix["stale"] else 0.55,
            })
        elif vix_val < 14:
            signals.append({
                "factor": "low_market_fear",
                "category": "macro",
                "impact": "positive",
                "strength": min((20 - vix_val) / 15, 1.0),
                "confidence": 0.75 if not vix["stale"] else 0.55,
            })

    # Signal 3: CPI shift
    cpi = macro_data.get("cpi")
    if cpi and cpi["change_pct"] is not None:
        cpi_change = cpi["change_pct"]
        if abs(cpi_change) > 0.5:
            signals.append({
                "factor": "cpi_shift",
                "category": "macro",
                "impact": "negative" if cpi_change > 0.3 else "positive",
                "strength": min(abs(cpi_change) / 2, 1.0),
                "confidence": 0.60 if not cpi["stale"] else 0.40,
            })

    return signals


def get_macro_context(db: Session, end_date: str) -> dict:
    """Get current macro context for the explanation output."""
    context = {}
    for indicator in ["fed_funds_rate", "vix", "cpi", "unemployment_rate"]:
        row = db.execute(text("""
            SELECT value, date::date FROM macro_events
            WHERE indicator = :ind AND date <= :end_date
            ORDER BY date DESC LIMIT 1
        """), {"ind": indicator, "end_date": end_date}).fetchone()

        if row:
            context[indicator] = {
                "value": float(row[0]) if row[0] else None,
                "date": str(row[1]),
                "fresh": not _is_stale(str(row[1]), end_date, indicator),
            }

    return context


def _is_stale(data_date: str, end_date: str, indicator: str) -> bool:
    """Check if macro data is too old to be relevant."""
    from datetime import datetime
    d1 = datetime.strptime(data_date, "%Y-%m-%d")
    d2 = datetime.strptime(end_date, "%Y-%m-%d")
    days_old = (d2 - d1).days

    # Different staleness thresholds per indicator
    thresholds = {
        "fed_funds_rate": 7,
        "vix": 3,
        "cpi": 45,
        "unemployment_rate": 45,
    }
    return days_old > thresholds.get(indicator, 30)
