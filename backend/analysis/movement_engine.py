"""
Movement Attribution Engine

The main pipeline that orchestrates signal extraction, scoring,
driver selection, and structured explanation generation.

Pipeline:
    1. Resolve ticker → company_id
    2. Collect aligned data
    3. Extract signals (price, volume, sector, macro, event)
    4. Compute data quality
    5. Score signals → select top drivers
    6. Build structured explanation
    7. Cache result

The LLM is NOT called here. This engine produces deterministic,
structured output. The presentation layer formats it.
"""

import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text
from sqlalchemy.orm import Session
from loguru import logger

from backend.analysis.signals.price_signals import extract_price_signals, compute_support_resistance
from backend.analysis.signals.volume_signals import extract_volume_signals
from backend.analysis.signals.sector_signals import extract_sector_signals
from backend.analysis.signals.macro_signals import extract_macro_signals, get_macro_context
from backend.analysis.signals.event_signals import extract_event_signals, get_event_context
from backend.analysis.scoring.signal_scorer import score_and_select_drivers, compute_data_quality


RANGE_TO_DAYS = {"1d": 1, "7d": 7, "14d": 14, "30d": 30, "90d": 90}


def explain_movement(db: Session, ticker: str, range_str: str = "7d") -> dict:
    """
    Main entry point for the Movement Attribution Engine.

    Args:
        db: SQLAlchemy session
        ticker: stock ticker (e.g., AAPL)
        range_str: lookback period (1d, 7d, 30d)

    Returns:
        Structured explanation dict with drivers, context, confidence
    """
    ticker = ticker.upper()
    lookback_days = RANGE_TO_DAYS.get(range_str, 7)

    # Step 1: Check cache (TTL: 6 hours)
    cached = _check_cache(db, ticker, range_str)
    if cached:
        return cached

    # Step 2: Resolve ticker
    company = db.execute(text("""
        SELECT c.id, c.ticker, c.name, sec.name, sec.display_name
        FROM companies c
        LEFT JOIN sectors sec ON c.sector_id = sec.id
        WHERE c.ticker = :ticker
    """), {"ticker": ticker}).fetchone()

    if not company:
        return {"error": f"Ticker '{ticker}' not found"}

    company_id, _, company_name, sector_name, sector_display = company

    # Step 3: Resolve end date (latest trading day)
    end_date_row = db.execute(text("""
        SELECT MAX(date)::date FROM stocks WHERE company_id = :cid
    """), {"cid": company_id}).fetchone()

    if not end_date_row or not end_date_row[0]:
        return {"error": f"No price data for {ticker}"}

    end_date = str(end_date_row[0])

    # Step 4: Get period return
    prices = db.execute(text("""
        SELECT date::date, close FROM stocks
        WHERE company_id = :cid AND date <= :end_date
        ORDER BY date DESC LIMIT :limit
    """), {"cid": company_id, "end_date": end_date, "limit": lookback_days + 1}).fetchall()

    if len(prices) < 2:
        return {"error": f"Insufficient price data for {ticker}"}

    latest_close = float(prices[0][1])
    start_close = float(prices[-1][1])
    period_return = round(((latest_close - start_close) / start_close) * 100, 2) if start_close > 0 else 0

    # Step 5: Extract signals from all modules
    all_signals = []
    has_indicators = False
    has_macro = False
    has_events = False
    macro_fresh = False

    try:
        price_sigs = extract_price_signals(db, company_id, ticker, end_date, lookback_days)
        all_signals.extend(price_sigs)
        has_indicators = len(price_sigs) > 0
    except Exception as e:
        logger.warning(f"Price signal extraction failed for {ticker}: {e}")
        try: db.rollback()
        except: pass

    try:
        vol_sigs = extract_volume_signals(db, company_id, ticker, end_date, lookback_days)
        all_signals.extend(vol_sigs)
    except Exception as e:
        logger.warning(f"Volume signal extraction failed for {ticker}: {e}")
        try: db.rollback()
        except: pass

    try:
        sector_sigs = extract_sector_signals(db, company_id, ticker, end_date, lookback_days)
        all_signals.extend(sector_sigs)
    except Exception as e:
        logger.warning(f"Sector signal extraction failed for {ticker}: {e}")
        try: db.rollback()
        except: pass

    try:
        macro_sigs = extract_macro_signals(db, company_id, ticker, end_date, lookback_days)
        all_signals.extend(macro_sigs)
        has_macro = len(macro_sigs) > 0
        macro_fresh = any(s.get("confidence", 0) > 0.6 for s in macro_sigs)
    except Exception as e:
        logger.warning(f"Macro signal extraction failed for {ticker}: {e}")
        try: db.rollback()
        except: pass

    try:
        event_sigs = extract_event_signals(db, company_id, ticker, end_date, lookback_days)
        all_signals.extend(event_sigs)
        has_events = len(event_sigs) > 0
    except Exception as e:
        logger.warning(f"Event signal extraction failed for {ticker}: {e}")
        try: db.rollback()
        except: pass

    # Step 6: Compute data quality
    data_quality = compute_data_quality(
        has_indicators=has_indicators,
        has_macro=has_macro,
        has_events=has_events,
        macro_fresh=macro_fresh,
    )

    # Step 7: Score and select top drivers
    scored = score_and_select_drivers(all_signals, data_quality)

    # Step 8: Get support/resistance
    sr = compute_support_resistance(db, company_id, end_date)

    # Step 9: Get context
    macro_ctx = get_macro_context(db, end_date)
    event_ctx = get_event_context(db, ticker, end_date, lookback_days)

    # Step 10: Get technical indicators for display
    ind = db.execute(text("""
        SELECT ma20, ma50, ma200, rsi, macd, macd_signal, volatility_20d, volume_ratio, trend_direction
        FROM daily_indicators
        WHERE company_id = :cid AND date <= :end_date
        ORDER BY date DESC LIMIT 1
    """), {"cid": company_id, "end_date": end_date}).fetchone()

    technical_context = {}
    if ind:
        technical_context = {
            "ma20": float(ind[0]) if ind[0] else None,
            "ma50": float(ind[1]) if ind[1] else None,
            "ma200": float(ind[2]) if ind[2] else None,
            "rsi": float(ind[3]) if ind[3] else None,
            "macd": float(ind[4]) if ind[4] else None,
            "volatility_20d": float(ind[6]) if ind[6] else None,
            "volume_ratio": float(ind[7]) if ind[7] else None,
            "trend": ind[8] or "unknown",
            "support": sr.get("support"),
            "resistance": sr.get("resistance"),
        }

    # Build buy/sell zones
    buy_sell = _compute_buy_sell_zones(latest_close, sr, technical_context)

    # Step 11: Build summary
    direction = "rose" if period_return > 0.5 else "fell" if period_return < -0.5 else "was flat"
    summary = (
        f"{ticker} {direction} {abs(period_return):.1f}% over {range_str}"
        f" (${start_close:.2f} → ${latest_close:.2f})"
    )

    # Step 12: Assemble final result
    result = {
        "ticker": ticker,
        "name": company_name,
        "sector": sector_display,
        "range": range_str,
        "period_return": period_return,
        "latest_close": latest_close,
        "summary": summary,
        "drivers": scored["drivers"],
        "technical_context": technical_context,
        "macro_context": macro_ctx,
        "event_context": event_ctx[:5],
        "buy_sell_zones": buy_sell,
        "overall_confidence": scored["overall_confidence"],
        "confidence_breakdown": scored["confidence_breakdown"],
        "data_quality": data_quality,
        "signals_analyzed": scored["all_signals_count"],
        "methodology": [
            "multi-factor attribution",
            "time-aligned signal analysis",
            "confidence-weighted scoring",
        ],
        "model_version": "v1.0_attribution_engine",
        "disclaimer": "AI-generated estimate based on historical data. Not financial advice.",
    }

    # Step 13: Cache
    _store_cache(db, ticker, range_str, result)

    return result


def _compute_buy_sell_zones(close: float, sr: dict, tech: dict) -> dict:
    """Compute statistical support/resistance zones."""
    support = sr.get("support")
    resistance = sr.get("resistance")
    ma50 = tech.get("ma50")

    buy_zone = {}
    sell_zone = {}

    if support:
        buy_low = round(support * 0.99, 2)
        buy_high = round(support * 1.01, 2)
        method = "Support cluster"
        if ma50 and abs(float(ma50) - support) / support < 0.03:
            method += " + MA50 confluence"
        buy_zone = {"low": buy_low, "high": buy_high, "method": method}

    if resistance:
        sell_low = round(resistance * 0.99, 2)
        sell_high = round(resistance * 1.01, 2)
        sell_zone = {"low": sell_low, "high": sell_high, "method": "Resistance cluster"}

    return {
        "buy_zone": buy_zone if buy_zone else None,
        "sell_zone": sell_zone if sell_zone else None,
        "label": "Statistical support/resistance zones based on historical reactions",
    }


def _check_cache(db: Session, ticker: str, range_str: str) -> dict | None:
    """Check if a recent cached result exists (TTL: 6 hours)."""
    try:
        row = db.execute(text("""
            SELECT result_json, generated_at FROM movement_cache
            WHERE ticker = :ticker AND range_period = :range
            ORDER BY generated_at DESC LIMIT 1
        """), {"ticker": ticker, "range": range_str}).fetchone()

        if row:
            generated = row[1]
            if (datetime.now() - generated).total_seconds() < 6 * 3600:
                return row[0]
    except Exception:
        pass
    return None


def _store_cache(db: Session, ticker: str, range_str: str, result: dict) -> None:
    """Store result in movement cache."""
    try:
        import json
        result_json = json.dumps(result, default=str)
        db.execute(text("""
            INSERT INTO movement_cache (ticker, range_period, result_json)
            VALUES (:ticker, :range, CAST(:result AS JSON))
        """), {"ticker": ticker, "range": range_str, "result": result_json})
        db.commit()
    except Exception as e:
        logger.warning(f"Cache store failed: {e}")
        try:
            db.rollback()
        except Exception:
            pass
