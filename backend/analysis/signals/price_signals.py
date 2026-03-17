"""
Price Signal Extractor

Extracts price-based signals from daily indicators and stock data.
Signals: trend direction, momentum strength, support/resistance zones,
moving average alignment, RSI conditions.

Each signal outputs the standard format:
    {factor, category, impact, strength, confidence}
"""

from sqlalchemy import text
from sqlalchemy.orm import Session


def extract_price_signals(db: Session, company_id: int, ticker: str, end_date: str, lookback_days: int = 30) -> list[dict]:
    """
    Extract all price-based signals for the given company and date range.
    Uses precomputed daily_indicators — no runtime calculation.
    """
    signals = []

    # Get latest indicators
    ind = db.execute(text("""
        SELECT ma20, ma50, ma200, rsi, macd, macd_signal, macd_histogram,
               volatility_20d, trend_direction
        FROM daily_indicators
        WHERE company_id = :cid AND date <= :end_date
        ORDER BY date DESC LIMIT 1
    """), {"cid": company_id, "end_date": end_date}).fetchone()

    if not ind:
        return signals

    ma20, ma50, ma200, rsi, macd, macd_sig, macd_hist, vol_20d, trend = ind

    # Get recent price data for return computation
    prices = db.execute(text("""
        SELECT date::date, close, pct_change
        FROM stocks
        WHERE company_id = :cid AND date <= :end_date
        ORDER BY date DESC LIMIT :limit
    """), {"cid": company_id, "end_date": end_date, "limit": lookback_days + 1}).fetchall()

    if len(prices) < 2:
        return signals

    latest_close = float(prices[0][1])
    period_return = _compute_period_return(prices, lookback_days)

    # Signal 1: Trend Direction
    if trend and ma20 and ma50:
        if trend == "bullish":
            signals.append({
                "factor": "price_trend_bullish",
                "category": "price",
                "impact": "positive",
                "strength": min(abs(period_return) / 10, 1.0) if period_return and period_return > 0 else 0.3,
                "confidence": 0.85 if ma200 and float(ma20) > float(ma200) else 0.65,
            })
        elif trend == "bearish":
            signals.append({
                "factor": "price_trend_bearish",
                "category": "price",
                "impact": "negative",
                "strength": min(abs(period_return) / 10, 1.0) if period_return and period_return < 0 else 0.3,
                "confidence": 0.85 if ma200 and float(ma20) < float(ma200) else 0.65,
            })

    # Signal 2: RSI Conditions
    if rsi:
        rsi_val = float(rsi)
        if rsi_val > 70:
            signals.append({
                "factor": "rsi_overbought",
                "category": "price",
                "impact": "negative",
                "strength": min((rsi_val - 70) / 30, 1.0),
                "confidence": 0.75,
            })
        elif rsi_val < 30:
            signals.append({
                "factor": "rsi_oversold",
                "category": "price",
                "impact": "positive",
                "strength": min((30 - rsi_val) / 30, 1.0),
                "confidence": 0.75,
            })

    # Signal 3: MACD Crossover
    if macd and macd_sig:
        macd_val = float(macd)
        sig_val = float(macd_sig)
        hist_val = float(macd_hist) if macd_hist else 0

        if macd_val > sig_val and hist_val > 0:
            signals.append({
                "factor": "macd_bullish_crossover",
                "category": "price",
                "impact": "positive",
                "strength": min(abs(hist_val) / 2, 1.0),
                "confidence": 0.70,
            })
        elif macd_val < sig_val and hist_val < 0:
            signals.append({
                "factor": "macd_bearish_crossover",
                "category": "price",
                "impact": "negative",
                "strength": min(abs(hist_val) / 2, 1.0),
                "confidence": 0.70,
            })

    # Signal 4: Moving Average Alignment (Golden/Death Cross proximity)
    if ma50 and ma200:
        ma50_val = float(ma50)
        ma200_val = float(ma200)
        ma_spread = (ma50_val - ma200_val) / ma200_val * 100

        if ma_spread > 0:
            signals.append({
                "factor": "ma_golden_alignment",
                "category": "price",
                "impact": "positive",
                "strength": min(ma_spread / 10, 1.0),
                "confidence": 0.80,
            })
        elif ma_spread < -2:
            signals.append({
                "factor": "ma_death_alignment",
                "category": "price",
                "impact": "negative",
                "strength": min(abs(ma_spread) / 10, 1.0),
                "confidence": 0.80,
            })

    # Signal 5: Volatility
    if vol_20d:
        vol_val = float(vol_20d)
        if vol_val > 3:
            signals.append({
                "factor": "high_volatility",
                "category": "price",
                "impact": "neutral",
                "strength": min(vol_val / 5, 1.0),
                "confidence": 0.85,
            })

    return signals


def compute_support_resistance(db: Session, company_id: int, end_date: str) -> dict:
    """
    Compute support and resistance levels from recent price clusters.
    Uses local minima/maxima over the last 60 trading days.
    """
    prices = db.execute(text("""
        SELECT close FROM stocks
        WHERE company_id = :cid AND date <= :end_date AND close IS NOT NULL
        ORDER BY date DESC LIMIT 60
    """), {"cid": company_id, "end_date": end_date}).fetchall()

    if len(prices) < 10:
        return {"support": None, "resistance": None}

    closes = [float(p[0]) for p in prices]
    latest = closes[0]
    sorted_prices = sorted(closes)

    # Support: cluster of prices below current that held
    below = [p for p in sorted_prices if p < latest]
    above = [p for p in sorted_prices if p > latest]

    support = round(below[len(below) // 4], 2) if len(below) > 4 else None  # 25th percentile below
    resistance = round(above[len(above) * 3 // 4], 2) if len(above) > 4 else None  # 75th percentile above

    return {
        "support": support,
        "resistance": resistance,
        "method": "60-day price cluster analysis",
    }


def _compute_period_return(prices: list, days: int) -> float | None:
    """Compute return over the lookback period."""
    if len(prices) < 2:
        return None
    end_close = float(prices[0][1])
    start_idx = min(days, len(prices) - 1)
    start_close = float(prices[start_idx][1])
    if start_close <= 0:
        return None
    return round(((end_close - start_close) / start_close) * 100, 2)
