"""
Presentation Mapper

Converts internal signal factors into analyst-style explanations
that read like a financial briefing, not a quant report.

Rules:
    - Speak like a Bloomberg analyst, not a robot
    - Say what it MEANS for the investor, not what the indicator IS
    - Short labels should be action-oriented
    - Never expose raw factor names
"""

FACTOR_MAP = {
    # ── Price signals ──────────────────────────────────────
    "price_trend_bullish": {
        "positive": "The stock has been steadily climbing — buyers are in control and momentum is building",
        "short": "Price gaining strength",
        "icon": "trending_up",
    },
    "price_trend_bearish": {
        "negative": "The stock has been sliding lower — sellers are dominating and the trend is working against it",
        "short": "Price losing ground",
        "icon": "trending_down",
    },
    "rsi_overbought": {
        "negative": "The rally has been aggressive — the stock is stretched far above normal levels and may need to cool off",
        "short": "May be overheated",
        "icon": "warning",
    },
    "rsi_oversold": {
        "positive": "The sell-off has been overdone — the stock is trading well below normal levels, which often attracts buyers",
        "short": "Potentially undervalued",
        "icon": "opportunity",
    },
    "macd_bullish_crossover": {
        "positive": "Buying momentum is picking up — the stock just flipped from weakening to strengthening",
        "short": "Momentum turning positive",
        "icon": "trending_up",
    },
    "macd_bearish_crossover": {
        "negative": "Selling pressure is building — the stock just shifted from gaining to losing momentum",
        "short": "Momentum turning negative",
        "icon": "trending_down",
    },
    "ma_golden_alignment": {
        "positive": "The stock is trading above its key long-term averages — this is a healthy bullish setup that institutions watch closely",
        "short": "Strong long-term setup",
        "icon": "trending_up",
    },
    "ma_death_alignment": {
        "negative": "The stock has fallen below its major moving averages — this is a bearish pattern that often signals more downside ahead",
        "short": "Weak long-term setup",
        "icon": "trending_down",
    },
    "high_volatility": {
        "neutral": "The stock is swinging more than usual — big moves in either direction are possible right now",
        "short": "Wild price swings",
        "icon": "warning",
    },

    # ── Volume signals ─────────────────────────────────────
    "volume_spike": {
        "positive": "A surge of buying interest hit the stock — big money is piling in and driving the price up",
        "negative": "Heavy selling volume hit the stock — large investors appear to be dumping shares",
        "short": "Unusual activity detected",
        "icon": "volume_up",
    },
    "volume_dryup": {
        "neutral": "Trading activity has gone quiet — fewer investors are participating, which often means the market is waiting for a catalyst",
        "short": "Market waiting for a catalyst",
        "icon": "volume_down",
    },
    "price_volume_divergence": {
        "negative": "The price is rising but on shrinking volume — this rally may not have strong conviction behind it",
        "short": "Rally looks fragile",
        "icon": "warning",
    },

    # ── Sector signals ─────────────────────────────────────
    "sector_outperformance": {
        "positive": "This stock is beating the rest of its sector — something company-specific is driving it higher",
        "short": "Leading its sector",
        "icon": "star",
    },
    "sector_underperformance": {
        "negative": "While the rest of the sector is doing fine, this stock is falling behind — something specific is holding it back",
        "short": "Lagging its sector",
        "icon": "trending_down",
    },
    "sector_momentum": {
        "positive": "The entire sector is rallying right now — this stock is riding the wave along with its peers",
        "negative": "The whole sector is under pressure — this stock is getting dragged down with the group",
        "short": "Sector-wide move",
        "icon": "group",
    },
    "sector_divergence": {
        "neutral": "This stock is moving opposite to its sector — it's going its own way, which suggests a company-specific story",
        "short": "Breaking from the pack",
        "icon": "warning",
    },

    # ── Macro signals ──────────────────────────────────────
    "high_interest_rate_environment": {
        "negative": "Interest rates are elevated — this makes borrowing expensive and puts pressure on stock valuations across the board",
        "short": "High rates weighing on stocks",
        "icon": "macro",
    },
    "low_interest_rate_environment": {
        "positive": "Interest rates are low — cheap money tends to flow into stocks, boosting valuations",
        "short": "Low rates supporting stocks",
        "icon": "macro",
    },
    "elevated_market_fear": {
        "negative": "The market fear index is spiking — investors are nervous, and that's creating selling pressure everywhere",
        "short": "Investors are fearful",
        "icon": "warning",
    },
    "low_market_fear": {
        "positive": "Markets are calm and confident — low fear levels usually mean stocks have room to run",
        "short": "Markets are calm",
        "icon": "check",
    },
    "cpi_shift": {
        "negative": "Inflation just came in hot — this could push the Fed to keep rates higher for longer, which is bad for stocks",
        "positive": "Inflation is cooling down — this increases the chances of rate cuts, which would be a boost for stocks",
        "short": "Inflation data shifted",
        "icon": "macro",
    },

    # ── Event signals ──────────────────────────────────────
    "event_price_spike": {
        "positive": "The stock had a major spike during this period — likely driven by earnings, news, or a catalyst",
        "short": "Major price spike detected",
        "icon": "event",
    },
    "event_price_crash": {
        "negative": "The stock took a big hit during this period — a sudden drop that moved the needle significantly",
        "short": "Sharp drop detected",
        "icon": "event",
    },
    "market_market_crash": {
        "negative": "A broad market sell-off happened during this window — nearly everything got pulled down together",
        "short": "Market-wide sell-off",
        "icon": "event",
    },
    "market_sector_rally": {
        "positive": "A sector-wide rally swept through — multiple stocks in the group surged together",
        "short": "Sector rally wave",
        "icon": "event",
    },
    "market_sector_selloff": {
        "negative": "A sector-wide sell-off dragged the group lower — not just this stock, the whole sector got hit",
        "short": "Sector-wide sell-off",
        "icon": "event",
    },
}


def map_driver_to_explanation(driver: dict) -> dict:
    """
    Convert a raw driver signal into an analyst-style explanation.
    """
    factor = driver.get("factor", "")
    impact = driver.get("impact", "neutral")

    mapping = FACTOR_MAP.get(factor, {})

    explanation = mapping.get(impact, mapping.get("positive", mapping.get("negative", mapping.get("neutral", ""))))
    if not explanation:
        explanation = f"A notable signal was detected that may be influencing the stock's movement"

    short_label = mapping.get("short", factor.replace("_", " ").title())
    icon = mapping.get("icon", "info")

    return {
        **driver,
        "explanation": explanation,
        "short_label": short_label,
        "icon": icon,
    }


def map_all_drivers(drivers: list[dict]) -> list[dict]:
    """Map all drivers to analyst-style explanations."""
    return [map_driver_to_explanation(d) for d in drivers]


def generate_narrative_summary(ticker: str, period_return: float, range_str: str, drivers: list[dict]) -> str:
    """
    Generate a narrative paragraph summarizing why the stock moved.
    Reads like a morning briefing, not a data dump.
    """
    if not drivers:
        direction = "higher" if period_return > 0 else "lower" if period_return < 0 else "flat"
        return f"{ticker} moved {direction} by {abs(period_return):.1f}% over {range_str}, but no strong signals were detected to explain the move."

    direction = "gained" if period_return > 0.5 else "lost" if period_return < -0.5 else "held steady around"
    amount = f"{abs(period_return):.1f}%"

    # Get the top 2 drivers for the narrative
    top = drivers[:2]
    parts = []

    for d in top:
        label = d.get("short_label", "")
        impact = d.get("impact", "neutral")

        if impact == "positive":
            parts.append(f"supported by {label.lower()}")
        elif impact == "negative":
            parts.append(f"pressured by {label.lower()}")
        else:
            parts.append(f"amid {label.lower()}")

    if period_return > 0.5:
        narrative = f"{ticker} {direction} {amount} over the past {range_str}"
    elif period_return < -0.5:
        narrative = f"{ticker} {direction} {amount} over the past {range_str}"
    else:
        narrative = f"{ticker} {direction} {amount} over the past {range_str}"

    if parts:
        narrative += ", " + " and ".join(parts)

    narrative += "."

    # Add confidence note
    conf = drivers[0].get("confidence", 0) if drivers else 0
    if conf > 0.7:
        narrative += " The signal alignment is strong."
    elif conf < 0.4:
        narrative += " Signals are mixed — proceed with caution."

    return narrative
