"""
Investment Intelligence API Routes

POST /api/portfolio/holdings          — add a holding
GET  /api/portfolio/holdings          — list holdings
DELETE /api/portfolio/holdings/{id}   — remove a holding
GET  /api/portfolio/analysis          — full portfolio intelligence
GET  /api/investments/score/{ticker}  — investment score for a stock
GET  /api/investments/profile         — get user risk profile
POST /api/investments/profile         — set/update risk profile
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel

from backend.api.dependencies import get_db
from backend.analysis.investment_scorer import score_investment
from backend.analysis.portfolio_engine import analyze_portfolio

router = APIRouter(tags=["Investments"])

DEFAULT_USER = "demo_user_1"


# ── Request Models ──────────────────────────────────────────

class AddHoldingRequest(BaseModel):
    ticker: str
    quantity: float
    avg_buy_price: float
    asset_type: str = "stock"
    buy_date: Optional[str] = None
    notes: Optional[str] = None

class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    risk_tolerance: Optional[str] = None
    investment_horizon: Optional[str] = None


# ── Portfolio Endpoints ─────────────────────────────────────

@router.post("/api/portfolio/holdings")
def add_holding(req: AddHoldingRequest, db: Session = Depends(get_db)):
    """Add a stock or crypto to the portfolio."""
    ticker = req.ticker.upper()

    # Validate ticker exists
    if req.asset_type == "stock":
        exists = db.execute(text("SELECT id FROM companies WHERE ticker = :t"), {"t": ticker}).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail=f"Stock ticker '{ticker}' not found")
    elif req.asset_type == "crypto":
        exists = db.execute(text("SELECT id FROM crypto_assets WHERE symbol = :t"), {"t": ticker}).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail=f"Crypto '{ticker}' not found")

    # Ensure user profile exists
    _ensure_profile(db, DEFAULT_USER)

    # Check if holding already exists — update quantity if so
    existing = db.execute(text("""
        SELECT id, quantity, avg_buy_price FROM portfolio_holdings
        WHERE user_id = :uid AND ticker = :ticker AND asset_type = :atype
    """), {"uid": DEFAULT_USER, "ticker": ticker, "atype": req.asset_type}).fetchone()

    if existing:
        # Average up/down
        old_qty = float(existing[1])
        old_price = float(existing[2])
        new_qty = old_qty + req.quantity
        new_avg = ((old_qty * old_price) + (req.quantity * req.avg_buy_price)) / new_qty if new_qty > 0 else req.avg_buy_price

        db.execute(text("""
            UPDATE portfolio_holdings
            SET quantity = :qty, avg_buy_price = :price, updated_at = NOW()
            WHERE id = :id
        """), {"qty": new_qty, "price": round(new_avg, 4), "id": existing[0]})
        db.commit()

        return {"message": f"Updated {ticker} — now {new_qty} shares at ${new_avg:.2f} avg", "action": "updated"}

    # New holding
    db.execute(text("""
        INSERT INTO portfolio_holdings (user_id, asset_type, ticker, quantity, avg_buy_price, buy_date, notes)
        VALUES (:uid, :atype, :ticker, :qty, :price, :buy_date, :notes)
    """), {
        "uid": DEFAULT_USER, "atype": req.asset_type, "ticker": ticker,
        "qty": req.quantity, "price": req.avg_buy_price,
        "buy_date": req.buy_date, "notes": req.notes,
    })
    db.commit()

    return {"message": f"Added {req.quantity} shares of {ticker} at ${req.avg_buy_price:.2f}", "action": "added"}


@router.get("/api/portfolio/holdings")
def list_holdings(db: Session = Depends(get_db)):
    """List all portfolio holdings with current values."""
    holdings = db.execute(text("""
        SELECT id, ticker, asset_type, quantity, avg_buy_price, buy_date, notes
        FROM portfolio_holdings
        WHERE user_id = :uid
        ORDER BY created_at
    """), {"uid": DEFAULT_USER}).fetchall()

    result = []
    for h in holdings:
        ticker = h[1]
        asset_type = h[2]
        qty = float(h[3])
        buy_price = float(h[4])

        # Get current price
        if asset_type == "crypto":
            price_row = db.execute(text("""
                SELECT close FROM crypto_prices cp
                JOIN crypto_assets ca ON cp.crypto_id = ca.id
                WHERE ca.symbol = :t ORDER BY date DESC LIMIT 1
            """), {"t": ticker}).fetchone()
        else:
            price_row = db.execute(text("""
                SELECT s.close FROM stocks s JOIN companies c ON s.company_id = c.id
                WHERE c.ticker = :t ORDER BY s.date DESC LIMIT 1
            """), {"t": ticker}).fetchone()

        current_price = float(price_row[0]) if price_row else buy_price
        pnl = (current_price - buy_price) * qty
        pnl_pct = ((current_price - buy_price) / buy_price * 100) if buy_price > 0 else 0

        result.append({
            "id": h[0], "ticker": ticker, "asset_type": asset_type,
            "quantity": qty, "avg_buy_price": round(buy_price, 2),
            "current_price": round(current_price, 2),
            "current_value": round(qty * current_price, 2),
            "pnl": round(pnl, 2), "pnl_pct": round(pnl_pct, 2),
            "buy_date": str(h[5]) if h[5] else None,
            "notes": h[6],
        })

    return result


@router.delete("/api/portfolio/holdings/{holding_id}")
def delete_holding(holding_id: int, db: Session = Depends(get_db)):
    """Remove a holding from the portfolio."""
    existing = db.execute(text(
        "SELECT id, ticker FROM portfolio_holdings WHERE id = :id AND user_id = :uid"
    ), {"id": holding_id, "uid": DEFAULT_USER}).fetchone()

    if not existing:
        raise HTTPException(status_code=404, detail="Holding not found")

    db.execute(text("DELETE FROM portfolio_holdings WHERE id = :id"), {"id": holding_id})
    db.commit()

    return {"message": f"Removed {existing[1]} from portfolio"}


@router.get("/api/portfolio/analysis")
def portfolio_analysis(db: Session = Depends(get_db)):
    """Full portfolio intelligence analysis."""
    return analyze_portfolio(db, DEFAULT_USER)


# ── Investment Score Endpoint ───────────────────────────────

@router.get("/api/investments/score/{ticker}")
def investment_score(
    ticker: str,
    db: Session = Depends(get_db),
):
    """Get investment score for a stock."""
    # Get user profile for personalization
    profile = db.execute(text(
        "SELECT risk_tolerance FROM user_profiles WHERE user_id = :uid"
    ), {"uid": DEFAULT_USER}).fetchone()

    risk = profile[0] if profile else "moderate"

    result = score_investment(db, ticker, risk)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result


# ── Profile Endpoints ───────────────────────────────────────

@router.get("/api/investments/profile")
def get_profile(db: Session = Depends(get_db)):
    """Get the current user's investment profile."""
    _ensure_profile(db, DEFAULT_USER)

    row = db.execute(text("""
        SELECT user_id, name, risk_tolerance, investment_horizon, created_at
        FROM user_profiles WHERE user_id = :uid
    """), {"uid": DEFAULT_USER}).fetchone()

    return {
        "user_id": row[0], "name": row[1],
        "risk_tolerance": row[2], "investment_horizon": row[3],
        "created_at": str(row[4]),
    }


@router.post("/api/investments/profile")
def update_profile(req: UpdateProfileRequest, db: Session = Depends(get_db)):
    """Update the user's investment profile."""
    _ensure_profile(db, DEFAULT_USER)

    valid_risk = ["conservative", "moderate", "aggressive"]
    valid_horizon = ["short", "medium", "long"]

    if req.risk_tolerance and req.risk_tolerance not in valid_risk:
        raise HTTPException(status_code=400, detail=f"risk_tolerance must be one of: {valid_risk}")
    if req.investment_horizon and req.investment_horizon not in valid_horizon:
        raise HTTPException(status_code=400, detail=f"investment_horizon must be one of: {valid_horizon}")

    updates = []
    params = {"uid": DEFAULT_USER}

    if req.name:
        updates.append("name = :name")
        params["name"] = req.name
    if req.risk_tolerance:
        updates.append("risk_tolerance = :risk")
        params["risk"] = req.risk_tolerance
    if req.investment_horizon:
        updates.append("investment_horizon = :horizon")
        params["horizon"] = req.investment_horizon

    if updates:
        updates.append("updated_at = NOW()")
        query = f"UPDATE user_profiles SET {', '.join(updates)} WHERE user_id = :uid"
        db.execute(text(query), params)
        db.commit()

    return {"message": "Profile updated", "risk_tolerance": req.risk_tolerance, "investment_horizon": req.investment_horizon}


# ── Helpers ─────────────────────────────────────────────────

def _ensure_profile(db: Session, user_id: str):
    """Create default profile if it doesn't exist."""
    exists = db.execute(text("SELECT id FROM user_profiles WHERE user_id = :uid"), {"uid": user_id}).fetchone()
    if not exists:
        db.execute(text("""
            INSERT INTO user_profiles (user_id, name, risk_tolerance, investment_horizon)
            VALUES (:uid, 'Default User', 'moderate', 'medium')
        """), {"uid": user_id})
        db.commit()
