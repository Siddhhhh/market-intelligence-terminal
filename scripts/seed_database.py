"""
Market Intelligence Terminal — Full Database Seed

Runs the complete data ingestion pipeline:
    1. S&P 500 stock data (yfinance)
    2. Crypto data (CoinGecko)
    3. Macroeconomic data (FRED)
    4. Event detection

Run from project root:
    python scripts/seed_database.py

This will take a significant amount of time on first run:
    - Stocks: 30-60 minutes (500 companies × 35 years)
    - Crypto: 2-5 minutes (3 assets)
    - Macro: 1-2 minutes (6 indicators)
    - Events: 1-2 minutes (detection queries)

The pipeline is idempotent — safe to re-run without creating duplicates.
"""

import sys
import os
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger


def main():
    start_time = time.time()

    print()
    logger.info("=" * 60)
    logger.info("  MARKET INTELLIGENCE TERMINAL — FULL DATA SEED")
    logger.info("=" * 60)
    print()

    # ── Step 1: Stocks ──────────────────────────────────────
    logger.info("STEP 1/4: Ingesting S&P 500 stock data...")
    try:
        from backend.data_pipeline.stocks import ingest_sp500
        stock_result = ingest_sp500()
        logger.info(f"  Stocks done: {stock_result}")
    except Exception as e:
        logger.error(f"  Stock ingestion failed: {e}")
        stock_result = {"error": str(e)}

    print()

    # ── Step 2: Crypto ──────────────────────────────────────
    logger.info("STEP 2/4: Ingesting crypto data...")
    try:
        from backend.data_pipeline.crypto import ingest_crypto
        crypto_result = ingest_crypto()
        logger.info(f"  Crypto done: {crypto_result}")
    except Exception as e:
        logger.error(f"  Crypto ingestion failed: {e}")
        crypto_result = {"error": str(e)}

    print()

    # ── Step 3: Macro ───────────────────────────────────────
    logger.info("STEP 3/4: Ingesting macroeconomic data...")
    try:
        from backend.data_pipeline.macro import ingest_macro
        macro_result = ingest_macro()
        logger.info(f"  Macro done: {macro_result}")
    except Exception as e:
        logger.error(f"  Macro ingestion failed: {e}")
        macro_result = {"error": str(e)}

    print()

    # ── Step 4: Events ──────────────────────────────────────
    logger.info("STEP 4/4: Running event detection...")
    try:
        from backend.data_pipeline.events import detect_all_events
        event_result = detect_all_events()
        logger.info(f"  Events done: {event_result}")
    except Exception as e:
        logger.error(f"  Event detection failed: {e}")
        event_result = {"error": str(e)}

    # ── Summary ─────────────────────────────────────────────
    elapsed = time.time() - start_time
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    print()
    logger.info("=" * 60)
    logger.info("  SEED COMPLETE")
    logger.info(f"  Time elapsed: {minutes}m {seconds}s")
    logger.info(f"  Stocks:  {stock_result}")
    logger.info(f"  Crypto:  {crypto_result}")
    logger.info(f"  Macro:   {macro_result}")
    logger.info(f"  Events:  {event_result}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
