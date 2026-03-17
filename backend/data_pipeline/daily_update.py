"""
Daily Update Pipeline

Fetches only the latest data (last 5 trading days) instead of the full
historical range. Designed to run daily after market close.

This is much faster than the full ingestion — updates ~500 stocks in
2-5 minutes instead of 30-60 minutes.

Usage:
    from backend.data_pipeline.daily_update import run_daily_update
    result = run_daily_update()
"""

import sys
import os
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pandas as pd
import numpy as np
import yfinance as yf
from sqlalchemy import text
from loguru import logger
from tqdm import tqdm

from config import settings
from database.session import engine


def run_daily_update() -> dict:
    """
    Run the full daily update pipeline.

    Steps:
        1. Fetch latest stock prices (last 5 days for all companies)
        2. Fetch latest crypto prices
        3. Fetch latest macro data
        4. Run event detection on new data
        5. Update sector performance for new dates

    Returns a summary dict with counts for each step.
    """
    start_time = time.time()
    results = {}

    logger.info("=" * 60)
    logger.info("  DAILY UPDATE PIPELINE")
    logger.info(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    # Step 1: Update stocks
    try:
        logger.info("\n[1/5] Updating stock prices...")
        results["stocks"] = _update_stocks()
    except Exception as e:
        logger.error(f"Stock update failed: {e}")
        results["stocks"] = {"error": str(e)}

    # Step 2: Update crypto
    try:
        logger.info("\n[2/5] Updating crypto prices...")
        results["crypto"] = _update_crypto()
    except Exception as e:
        logger.error(f"Crypto update failed: {e}")
        results["crypto"] = {"error": str(e)}

    # Step 3: Update macro
    try:
        logger.info("\n[3/5] Updating macro data...")
        from backend.data_pipeline.macro import ingest_macro
        # Only fetch last 30 days of macro data
        thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        results["macro"] = ingest_macro(start_date=thirty_days_ago)
    except Exception as e:
        logger.error(f"Macro update failed: {e}")
        results["macro"] = {"error": str(e)}

    # Step 4: Run event detection
    try:
        logger.info("\n[4/5] Running event detection...")
        from backend.data_pipeline.events import detect_all_events
        results["events"] = detect_all_events()
    except Exception as e:
        logger.error(f"Event detection failed: {e}")
        results["events"] = {"error": str(e)}

    # Step 5: Update sector performance
    try:
        logger.info("\n[5/5] Updating sector performance...")
        from backend.data_pipeline.sector_engine import compute_sector_performance
        results["sectors"] = compute_sector_performance()
    except Exception as e:
        logger.error(f"Sector performance update failed: {e}")
        results["sectors"] = {"error": str(e)}

    elapsed = time.time() - start_time
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    logger.info("")
    logger.info("=" * 60)
    logger.info("  DAILY UPDATE COMPLETE")
    logger.info(f"  Time: {minutes}m {seconds}s")
    for step, result in results.items():
        logger.info(f"  {step}: {result}")
    logger.info("=" * 60)

    results["elapsed_seconds"] = round(elapsed, 1)
    return results


def _update_stocks() -> dict:
    """
    Fetch last 5 trading days of data for all active companies.
    Much faster than full historical download — only new data.
    """
    # Get all active company tickers
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, ticker FROM companies WHERE is_active = TRUE ORDER BY ticker"
        )).fetchall()

    ticker_to_id = {r[1]: r[0] for r in rows}
    tickers = list(ticker_to_id.keys())
    logger.info(f"  Updating {len(tickers)} companies...")

    start_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
    total_inserted = 0
    errors = 0

    for ticker in tqdm(tickers, desc="Updating stocks", unit="company"):
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(start=start_date, auto_adjust=True)

            if df.empty:
                continue

            df = df.reset_index()
            df = df.rename(columns={
                "Date": "date", "Open": "open", "High": "high",
                "Low": "low", "Close": "close", "Volume": "volume",
            })
            df = df[["date", "open", "high", "low", "close", "volume"]].copy()

            if df["date"].dt.tz is None:
                df["date"] = df["date"].dt.tz_localize("UTC")
            else:
                df["date"] = df["date"].dt.tz_convert("UTC")

            df["pct_change"] = df["close"].pct_change() * 100
            df["pct_change"] = df["pct_change"].round(4)
            df = df.dropna(subset=["close"])
            df = df.replace({np.nan: None})

            company_id = ticker_to_id[ticker]
            batch = []
            for _, r in df.iterrows():
                batch.append({
                    "date": r["date"],
                    "company_id": company_id,
                    "open": r["open"], "high": r["high"],
                    "low": r["low"], "close": r["close"],
                    "volume": int(r["volume"]) if r["volume"] is not None else None,
                    "pct_change": r["pct_change"],
                })

            if batch:
                with engine.connect() as conn:
                    conn.execute(text("""
                        INSERT INTO stocks (date, company_id, open, high, low, close, volume, pct_change)
                        VALUES (:date, :company_id, :open, :high, :low, :close, :volume, :pct_change)
                        ON CONFLICT DO NOTHING
                    """), batch)
                    conn.commit()
                total_inserted += len(batch)

        except Exception as e:
            errors += 1
            if errors <= 3:
                logger.warning(f"  Failed {ticker}: {e}")

        time.sleep(0.3)  # Faster rate for daily updates (less data per ticker)

    return {"rows_inserted": total_inserted, "companies": len(tickers), "errors": errors}


def _update_crypto() -> dict:
    """Fetch last 5 days of crypto data."""
    from backend.data_pipeline.crypto import ingest_crypto

    start_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
    return ingest_crypto(start_date=start_date)


if __name__ == "__main__":
    run_daily_update()
