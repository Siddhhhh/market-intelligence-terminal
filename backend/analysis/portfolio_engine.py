"""
Portfolio Intelligence Engine

Analyzes a user's portfolio for:
    - Total value and P&L
    - Sector distribution
    - Diversification score
    - Risk assessment
    - Actionable warnings and suggestions
"""

from sqlalchemy import text
from sqlalchemy.orm import Session
from loguru import logger


def analyze_portfolio(db: Session, user_id: str = "demo_user_1") -> dict:
    """
    Full portfolio intelligence analysis.

    Returns value, P&L, sector breakdown, diversification score,
    risk assessment, warnings, and suggestions.
    """
    # Get all holdings
    holdings = db.execute(text("""
        SELECT ph.id, ph.ticker, ph.asset_type, ph.quantity, ph.avg_buy_price,
               ph.buy_date, ph.notes
        FROM portfolio_holdings ph
        WHERE ph.user_id = :uid
        ORDER BY ph.created_at
    """), {"uid": user_id}).fetchall()

    if not holdings:
        return {
            "user_id": user_id,
            "total_value": 0,
            "total_cost": 0,
            "total_pnl": 0,
            "total_pnl_pct": 0,
            "holdings": [],
            "sector_breakdown": {},
            "diversification_score": 0,
            "risk_level": "none",
            "warnings": ["Portfolio is empty — add some holdings to get started"],
            "suggestions": [],
        }

    # Build holdings with current prices
    enriched = []
    sector_values = {}
    total_value = 0
    total_cost = 0

    for h in holdings:
        h_id, ticker, asset_type, qty, buy_price, buy_date, notes = h
        qty = float(qty)
        buy_price = float(buy_price)
        cost = qty * buy_price

        # Get current price
        if asset_type == "crypto":
            price_row = db.execute(text("""
                SELECT close FROM crypto_prices cp
                JOIN crypto_assets ca ON cp.crypto_id = ca.id
                WHERE ca.symbol = :ticker ORDER BY date DESC LIMIT 1
            """), {"ticker": ticker}).fetchone()
        else:
            price_row = db.execute(text("""
                SELECT s.close FROM stocks s
                JOIN companies c ON s.company_id = c.id
                WHERE c.ticker = :ticker ORDER BY s.date DESC LIMIT 1
            """), {"ticker": ticker}).fetchone()

        current_price = float(price_row[0]) if price_row and price_row[0] else buy_price
        current_value = qty * current_price
        pnl = current_value - cost
        pnl_pct = ((current_price - buy_price) / buy_price * 100) if buy_price > 0 else 0

        # Get sector
        sector = "Cryptocurrency" if asset_type == "crypto" else "Unknown"
        if asset_type == "stock":
            sec_row = db.execute(text("""
                SELECT sec.display_name FROM companies c
                JOIN sectors sec ON c.sector_id = sec.id
                WHERE c.ticker = :ticker
            """), {"ticker": ticker}).fetchone()
            sector = sec_row[0] if sec_row else "Unknown"

        sector_values[sector] = sector_values.get(sector, 0) + current_value
        total_value += current_value
        total_cost += cost

        enriched.append({
            "id": h_id,
            "ticker": ticker,
            "asset_type": asset_type,
            "quantity": qty,
            "avg_buy_price": round(buy_price, 2),
            "current_price": round(current_price, 2),
            "current_value": round(current_value, 2),
            "cost_basis": round(cost, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "sector": sector,
            "buy_date": str(buy_date) if buy_date else None,
            "notes": notes,
        })

    total_pnl = total_value - total_cost
    total_pnl_pct = ((total_value - total_cost) / total_cost * 100) if total_cost > 0 else 0

    # Sector breakdown as percentages
    sector_breakdown = {}
    for sector, value in sector_values.items():
        sector_breakdown[sector] = round((value / total_value * 100) if total_value > 0 else 0, 1)

    # Diversification score (0-100)
    diversification = _compute_diversification(sector_breakdown, len(enriched))

    # Risk level
    risk_level = _assess_risk(sector_breakdown, enriched, db)

    # Warnings and suggestions
    warnings, suggestions = _generate_insights(sector_breakdown, enriched, diversification, risk_level)

    # Get user profile
    profile = db.execute(text(
        "SELECT risk_tolerance, investment_horizon FROM user_profiles WHERE user_id = :uid"
    ), {"uid": user_id}).fetchone()

    return {
        "user_id": user_id,
        "risk_profile": profile[0] if profile else "moderate",
        "investment_horizon": profile[1] if profile else "medium",
        "total_value": round(total_value, 2),
        "total_cost": round(total_cost, 2),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": round(total_pnl_pct, 2),
        "holdings_count": len(enriched),
        "holdings": enriched,
        "sector_breakdown": sector_breakdown,
        "diversification_score": diversification,
        "risk_level": risk_level,
        "warnings": warnings,
        "suggestions": suggestions,
    }


def _compute_diversification(sector_breakdown: dict, holding_count: int) -> int:
    """
    Compute diversification score 0-100.

    Factors:
        - Number of holdings (more = better, up to 15)
        - Sector concentration (lower max % = better)
        - Number of sectors (more = better)
    """
    if not sector_breakdown or holding_count == 0:
        return 0

    # Holdings diversity (0-40 points)
    holding_score = min(holding_count / 15, 1.0) * 40

    # Sector count (0-30 points)
    sector_count = len(sector_breakdown)
    sector_score = min(sector_count / 8, 1.0) * 30

    # Concentration penalty (0-30 points)
    max_pct = max(sector_breakdown.values()) if sector_breakdown else 100
    if max_pct <= 25:
        conc_score = 30
    elif max_pct <= 40:
        conc_score = 20
    elif max_pct <= 60:
        conc_score = 10
    else:
        conc_score = 0

    return int(holding_score + sector_score + conc_score)


def _assess_risk(sector_breakdown: dict, holdings: list, db: Session) -> str:
    """Assess overall portfolio risk level."""
    if not holdings:
        return "none"

    # Check volatility of holdings
    high_vol_count = 0
    for h in holdings:
        if h["asset_type"] == "crypto":
            high_vol_count += 1
            continue

        vol_row = db.execute(text("""
            SELECT di.volatility_20d FROM daily_indicators di
            JOIN companies c ON di.company_id = c.id
            WHERE c.ticker = :ticker ORDER BY di.date DESC LIMIT 1
        """), {"ticker": h["ticker"]}).fetchone()

        if vol_row and vol_row[0] and float(vol_row[0]) > 3.0:
            high_vol_count += 1

    vol_ratio = high_vol_count / len(holdings) if holdings else 0

    max_sector_pct = max(sector_breakdown.values()) if sector_breakdown else 0

    if vol_ratio > 0.5 or max_sector_pct > 70:
        return "high"
    elif vol_ratio > 0.3 or max_sector_pct > 50:
        return "moderate"
    else:
        return "low"


def _generate_insights(sector_breakdown, holdings, diversification, risk_level) -> tuple:
    """Generate actionable warnings and suggestions."""
    warnings = []
    suggestions = []

    # Concentration warnings
    for sector, pct in sector_breakdown.items():
        if pct > 50:
            warnings.append(f"Heavy concentration in {sector} ({pct}%) — consider diversifying")
        elif pct > 35:
            warnings.append(f"Overweight in {sector} ({pct}%) — monitor exposure")

    # Diversification
    if diversification < 30:
        warnings.append("Portfolio diversification is very low — high risk of concentrated losses")
        suggestions.append("Consider adding holdings across different sectors")
    elif diversification < 50:
        suggestions.append("Adding 2-3 holdings in underrepresented sectors would improve diversification")

    # Holdings count
    if len(holdings) < 3:
        warnings.append("Very few holdings — a single bad trade could significantly impact your portfolio")
        suggestions.append("Consider building a portfolio of at least 5-10 positions")
    elif len(holdings) > 20:
        suggestions.append("You have many positions — consider consolidating into your highest conviction picks")

    # Missing sectors
    covered = set(sector_breakdown.keys())
    core_sectors = {"Technology", "Healthcare", "Financials", "Consumer Discretionary"}
    missing = core_sectors - covered
    if missing and len(holdings) >= 3:
        suggestions.append(f"No exposure to {', '.join(missing)} — these sectors add balance")

    # Risk level
    if risk_level == "high":
        warnings.append("Overall portfolio risk is high — volatility could cause significant swings")

    # P&L
    losers = [h for h in holdings if h["pnl_pct"] < -15]
    if losers:
        tickers = ", ".join(h["ticker"] for h in losers[:3])
        warnings.append(f"Significant losses in: {tickers} — review if thesis still holds")

    return warnings, suggestions
