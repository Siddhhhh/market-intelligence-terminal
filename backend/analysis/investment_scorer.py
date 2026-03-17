"""
Investment Scorer

Rates stocks on a 0-100 scale using multi-factor analysis.
Combines trend, fundamentals, momentum, risk, and sector signals
into a single investment score with a buy/hold/avoid rating.

Score mapping:
    80+ = Strong Buy
    65-79 = Buy
    40-64 = Hold
    Below 40 = Avoid

Each factor is scored 0-10 and weighted.
"""

from sqlalchemy import text
from sqlalchemy.orm import Session
from loguru import logger


WEIGHTS = {
    "trend": 0.25,
    "fundamentals": 0.20,
    "momentum": 0.20,
    "risk": 0.20,
    "sector": 0.15,
}

RISK_PROFILES = {
    "conservative": {"max_volatility": 2.0, "min_score": 65, "preferred_sectors": ["utilities", "consumer_staples", "healthcare"]},
    "moderate": {"max_volatility": 3.5, "min_score": 50, "preferred_sectors": []},
    "aggressive": {"max_volatility": 999, "min_score": 30, "preferred_sectors": ["technology", "consumer_discretionary"]},
}


def score_investment(db: Session, ticker: str, risk_profile: str = "moderate") -> dict:
    """
    Score a stock for investment quality.

    Returns a 0-100 score, rating, factor breakdown,
    risk level, and suitability for different profiles.
    """
    ticker = ticker.upper()

    company = db.execute(text("""
        SELECT c.id, c.ticker, c.name, sec.name as sector_name, sec.display_name
        FROM companies c
        LEFT JOIN sectors sec ON c.sector_id = sec.id
        WHERE c.ticker = :ticker
    """), {"ticker": ticker}).fetchone()

    if not company:
        return {"error": f"Ticker '{ticker}' not found"}

    company_id = company[0]
    sector_name = company[3] or "unknown"

    # Get latest indicators
    ind = db.execute(text("""
        SELECT ma20, ma50, ma200, rsi, macd, volatility_20d, volume_ratio, trend_direction
        FROM daily_indicators
        WHERE company_id = :cid ORDER BY date DESC LIMIT 1
    """), {"cid": company_id}).fetchone()

    # Get latest price
    price_row = db.execute(text("""
        SELECT close, pct_change FROM stocks
        WHERE company_id = :cid ORDER BY date DESC LIMIT 1
    """), {"cid": company_id}).fetchone()

    # Get fundamentals from cache
    fund = db.execute(text("""
        SELECT pe_ratio, revenue_growth, profit_margin, eps
        FROM company_cache WHERE ticker = :ticker
    """), {"ticker": ticker}).fetchone()

    # Score each factor
    trend_score = _score_trend(ind, price_row)
    fund_score = _score_fundamentals(fund)
    momentum_score = _score_momentum(ind)
    risk_score = _score_risk(ind)
    sector_score = _score_sector(db, company_id, sector_name)

    factors = {
        "trend": trend_score,
        "fundamentals": fund_score,
        "momentum": momentum_score,
        "risk": risk_score,
        "sector": sector_score,
    }

    # Weighted total
    total = sum(factors[k] * WEIGHTS[k] for k in factors)
    score = round(total * 10, 0)  # Scale to 0-100
    score = max(0, min(100, score))

    # Rating
    if score >= 80:
        rating = "Strong Buy"
    elif score >= 65:
        rating = "Buy"
    elif score >= 40:
        rating = "Hold"
    else:
        rating = "Avoid"

    # Risk level
    vol = float(ind[5]) if ind and ind[5] else 2.0
    if vol > 3.5:
        risk_level = "high"
    elif vol > 2.0:
        risk_level = "moderate"
    else:
        risk_level = "low"

    # Suitability
    suitable_for = []
    for profile, criteria in RISK_PROFILES.items():
        if vol <= criteria["max_volatility"] and score >= criteria["min_score"]:
            suitable_for.append(profile)

    # Check if suitable for the user's profile
    profile_match = risk_profile in suitable_for

    # Generate reasoning
    top_positive = sorted(factors.items(), key=lambda x: x[1], reverse=True)[:2]
    top_negative = sorted(factors.items(), key=lambda x: x[1])[:1]

    reasoning = []
    for name, val in top_positive:
        if val >= 7:
            reasoning.append(f"Strong {name} signals support this stock")
        elif val >= 5:
            reasoning.append(f"{name.title()} metrics are acceptable")

    for name, val in top_negative:
        if val < 4:
            reasoning.append(f"Weak {name} signals warrant caution")

    return {
        "ticker": ticker,
        "name": company[2],
        "sector": company[4],
        "score": int(score),
        "rating": rating,
        "factors": factors,
        "risk_level": risk_level,
        "suitable_for": suitable_for,
        "matches_profile": profile_match,
        "user_profile": risk_profile,
        "reasoning": reasoning,
        "current_price": float(price_row[0]) if price_row and price_row[0] else None,
        "disclaimer": "AI-generated investment score. Not financial advice.",
    }


def _score_trend(ind, price_row) -> float:
    """Score 0-10 based on price trend alignment."""
    if not ind:
        return 5.0

    score = 5.0
    trend = ind[7]  # trend_direction
    close = float(price_row[0]) if price_row and price_row[0] else 0
    ma50 = float(ind[1]) if ind[1] else 0
    ma200 = float(ind[2]) if ind[2] else 0

    if trend == "bullish":
        score += 2.5
    elif trend == "bearish":
        score -= 2.5

    if close and ma200 and close > ma200:
        score += 1.0
    elif close and ma200 and close < ma200:
        score -= 1.0

    if close and ma50 and close > ma50:
        score += 0.5
    elif close and ma50 and close < ma50:
        score -= 0.5

    return max(0, min(10, score))


def _score_fundamentals(fund) -> float:
    """Score 0-10 based on PE, growth, margins."""
    if not fund:
        return 5.0

    score = 5.0
    pe = float(fund[0]) if fund[0] else None
    growth = float(fund[1]) if fund[1] else None
    margin = float(fund[2]) if fund[2] else None

    if pe is not None:
        if 5 < pe < 20:
            score += 2.0
        elif 20 <= pe < 35:
            score += 0.5
        elif pe >= 35:
            score -= 1.0
        elif pe <= 0:
            score -= 2.0

    if growth is not None:
        if growth > 0.15:
            score += 2.0
        elif growth > 0.05:
            score += 1.0
        elif growth < -0.05:
            score -= 1.5

    if margin is not None:
        if margin > 0.20:
            score += 1.0
        elif margin < 0.05:
            score -= 1.0

    return max(0, min(10, score))


def _score_momentum(ind) -> float:
    """Score 0-10 based on RSI and MACD."""
    if not ind:
        return 5.0

    score = 5.0
    rsi = float(ind[3]) if ind[3] else 50
    macd = float(ind[4]) if ind[4] else 0

    if 40 < rsi < 60:
        score += 1.0  # Neutral is stable
    elif rsi > 70:
        score -= 1.5  # Overbought
    elif rsi < 30:
        score += 1.5  # Oversold = potential opportunity

    if macd > 0:
        score += 1.5
    elif macd < 0:
        score -= 1.0

    vol_ratio = float(ind[6]) if ind[6] else 1.0
    if vol_ratio > 1.5:
        score += 0.5  # Above average interest

    return max(0, min(10, score))


def _score_risk(ind) -> float:
    """Score 0-10 based on volatility (higher = lower score)."""
    if not ind:
        return 5.0

    vol = float(ind[5]) if ind[5] else 2.0

    if vol < 1.0:
        return 9.0
    elif vol < 1.5:
        return 8.0
    elif vol < 2.0:
        return 7.0
    elif vol < 2.5:
        return 6.0
    elif vol < 3.0:
        return 5.0
    elif vol < 4.0:
        return 3.5
    else:
        return 2.0


def _score_sector(db, company_id, sector_name) -> float:
    """Score 0-10 based on sector performance."""
    row = db.execute(text("""
        SELECT avg_pct_change FROM sector_performance sp
        JOIN sectors sec ON sp.sector_id = sec.id
        WHERE sec.name = :sector
        ORDER BY sp.date DESC LIMIT 1
    """), {"sector": sector_name}).fetchone()

    if not row:
        return 5.0

    avg = float(row[0]) if row[0] else 0

    if avg > 1.0:
        return 8.5
    elif avg > 0.5:
        return 7.0
    elif avg > 0:
        return 6.0
    elif avg > -0.5:
        return 4.5
    elif avg > -1.0:
        return 3.5
    else:
        return 2.0
