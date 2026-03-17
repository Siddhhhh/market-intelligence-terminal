"""
Technical Indicator Pipeline

Precomputes daily technical indicators (MA, RSI, MACD, volatility)
for all companies and stores them in the daily_indicators table.

Run:
    python -c "from backend.analysis.indicator_pipeline import compute_indicators; compute_indicators()"
"""

import sys
import os
import time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text
from loguru import logger
from database.session import engine


def compute_indicators(company_ids: list[int] = None):
    """
    Compute technical indicators for all (or specified) companies.

    For each company:
        1. Load full price history
        2. Compute MA20, MA50, MA200, RSI, MACD, volatility, volume_ratio
        3. Determine trend direction
        4. Insert into daily_indicators (ON CONFLICT DO NOTHING)
    """
    start_time = time.time()

    logger.info("=" * 60)
    logger.info("  INDICATOR PIPELINE")
    logger.info("=" * 60)

    with engine.connect() as conn:
        # Create table if not exists
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS daily_indicators (
                date DATE NOT NULL,
                company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
                ma20 NUMERIC(12,4),
                ma50 NUMERIC(12,4),
                ma200 NUMERIC(12,4),
                rsi NUMERIC(8,4),
                macd NUMERIC(10,4),
                macd_signal NUMERIC(10,4),
                macd_histogram NUMERIC(10,4),
                volatility_20d NUMERIC(8,4),
                volume_ratio NUMERIC(8,4),
                trend_direction VARCHAR(20),
                computed_at TIMESTAMP DEFAULT NOW(),
                PRIMARY KEY (date, company_id)
            )
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_daily_ind_company_date ON daily_indicators(company_id, date)
        """))
        conn.commit()

        # Get companies to process
        if company_ids:
            companies = conn.execute(text(
                "SELECT id, ticker FROM companies WHERE id = ANY(:ids) ORDER BY ticker"
            ), {"ids": company_ids}).fetchall()
        else:
            companies = conn.execute(text(
                "SELECT id, ticker FROM companies WHERE is_active = TRUE ORDER BY ticker"
            )).fetchall()

        logger.info(f"  Processing {len(companies)} companies...")

        total_rows = 0
        errors = 0

        for i, (cid, ticker) in enumerate(companies):
            try:
                rows = _compute_for_company(conn, cid, ticker)
                total_rows += rows

                if (i + 1) % 50 == 0:
                    elapsed = time.time() - start_time
                    rate = (i + 1) / elapsed
                    remaining = (len(companies) - i - 1) / rate if rate > 0 else 0
                    logger.info(
                        f"  Progress: {i+1}/{len(companies)} "
                        f"({rate:.1f}/sec, ~{remaining:.0f}s remaining)"
                    )
            except Exception as e:
                errors += 1
                if errors <= 5:
                    logger.warning(f"  Failed {ticker}: {e}")

        conn.commit()

    elapsed = time.time() - start_time
    logger.info("=" * 60)
    logger.info(f"  INDICATOR PIPELINE COMPLETE")
    logger.info(f"  {total_rows:,} rows, {len(companies)} companies, {errors} errors, {elapsed:.0f}s")
    logger.info("=" * 60)

    return {"rows": total_rows, "companies": len(companies), "errors": errors}


def _compute_for_company(conn, company_id: int, ticker: str) -> int:
    """Compute indicators for a single company using pandas for efficiency."""
    rows = conn.execute(text("""
        SELECT date::date, close, volume, pct_change
        FROM stocks
        WHERE company_id = :cid AND close IS NOT NULL
        ORDER BY date ASC
    """), {"cid": company_id}).fetchall()

    if len(rows) < 200:
        return 0  # Need at least 200 days for MA200

    df = pd.DataFrame(rows, columns=["date", "close", "volume", "pct_change"])
    df["close"] = df["close"].astype(float)
    df["volume"] = df["volume"].astype(float)
    df["pct_change"] = df["pct_change"].astype(float)

    # Moving averages
    df["ma20"] = df["close"].rolling(20).mean()
    df["ma50"] = df["close"].rolling(50).mean()
    df["ma200"] = df["close"].rolling(200).mean()

    # RSI (14-day)
    df["rsi"] = _compute_rsi(df["pct_change"], 14)

    # MACD (12, 26, 9)
    ema12 = df["close"].ewm(span=12).mean()
    ema26 = df["close"].ewm(span=26).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9).mean()
    df["macd_histogram"] = df["macd"] - df["macd_signal"]

    # Volatility (20-day rolling std of returns)
    df["volatility_20d"] = df["pct_change"].rolling(20).std()

    # Volume ratio (today / 20-day avg)
    vol_avg = df["volume"].rolling(20).mean()
    df["volume_ratio"] = df["volume"] / vol_avg.replace(0, np.nan)

    # Trend direction
    df["trend_direction"] = df.apply(
        lambda r: "bullish" if pd.notna(r["ma50"]) and pd.notna(r["ma200"]) and r["close"] > r["ma50"] > r["ma200"]
        else "bearish" if pd.notna(r["ma50"]) and pd.notna(r["ma200"]) and r["close"] < r["ma50"] < r["ma200"]
        else "neutral",
        axis=1,
    )

    # Only insert rows with MA200 computed (skip first 200 days)
    df = df.dropna(subset=["ma200"])
    df = df.replace({np.nan: None, np.inf: None, -np.inf: None})

    # Check which dates already exist
    existing = conn.execute(text("""
        SELECT date FROM daily_indicators WHERE company_id = :cid
    """), {"cid": company_id}).fetchall()
    existing_dates = {str(r[0]) for r in existing}

    # Filter to new dates only
    new_rows = df[~df["date"].astype(str).isin(existing_dates)]

    if new_rows.empty:
        return 0

    # Batch insert
    batch = []
    for _, r in new_rows.iterrows():
        batch.append({
            "date": r["date"],
            "company_id": company_id,
            "ma20": round(r["ma20"], 4) if r["ma20"] is not None else None,
            "ma50": round(r["ma50"], 4) if r["ma50"] is not None else None,
            "ma200": round(r["ma200"], 4) if r["ma200"] is not None else None,
            "rsi": round(r["rsi"], 4) if r["rsi"] is not None else None,
            "macd": round(r["macd"], 4) if r["macd"] is not None else None,
            "macd_signal": round(r["macd_signal"], 4) if r["macd_signal"] is not None else None,
            "macd_histogram": round(r["macd_histogram"], 4) if r["macd_histogram"] is not None else None,
            "volatility_20d": round(r["volatility_20d"], 4) if r["volatility_20d"] is not None else None,
            "volume_ratio": round(r["volume_ratio"], 4) if r["volume_ratio"] is not None else None,
            "trend_direction": r["trend_direction"],
        })

    if batch:
        conn.execute(text("""
            INSERT INTO daily_indicators
                (date, company_id, ma20, ma50, ma200, rsi, macd, macd_signal,
                 macd_histogram, volatility_20d, volume_ratio, trend_direction)
            VALUES
                (:date, :company_id, :ma20, :ma50, :ma200, :rsi, :macd, :macd_signal,
                 :macd_histogram, :volatility_20d, :volume_ratio, :trend_direction)
            ON CONFLICT DO NOTHING
        """), batch)

    return len(batch)


def _compute_rsi(returns: pd.Series, period: int = 14) -> pd.Series:
    """Compute RSI using exponential moving average of gains/losses."""
    delta = returns.copy()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)

    avg_gain = gain.ewm(alpha=1/period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


if __name__ == "__main__":
    compute_indicators()
