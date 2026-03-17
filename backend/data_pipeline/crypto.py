"""
Crypto Data Ingestion Pipeline

Downloads historical OHLCV data for BTC, ETH, and SOL using yfinance.
yfinance provides crypto data via tickers like BTC-USD, ETH-USD, SOL-USD.

This replaces the CoinGecko approach which now requires an API key.

Usage:
    from backend.data_pipeline.crypto import ingest_crypto
    ingest_crypto()
"""

import sys
import os
import time

import pandas as pd
import numpy as np
import yfinance as yf
from sqlalchemy import text
from loguru import logger

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import settings
from database.session import engine

# Mapping from our database symbols to yfinance tickers
CRYPTO_YFINANCE_MAP = {
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
    "SOL": "SOL-USD",
}


def get_crypto_assets() -> list[dict]:
    """Fetch crypto asset definitions from our database."""
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, symbol, name FROM crypto_assets WHERE is_active = TRUE"
        )).fetchall()

    assets = [{"id": r[0], "symbol": r[1], "name": r[2]} for r in rows]
    logger.info(f"  Found {len(assets)} active crypto assets in database")
    return assets


def download_crypto_history(symbol: str, start_date: str) -> pd.DataFrame:
    """
    Download historical crypto data using yfinance.

    Args:
        symbol: Our symbol (BTC, ETH, SOL)
        start_date: Start date string (YYYY-MM-DD)

    Returns:
        Cleaned DataFrame with OHLCV + pct_change
    """
    yf_ticker = CRYPTO_YFINANCE_MAP.get(symbol)
    if not yf_ticker:
        logger.warning(f"  No yfinance mapping for {symbol}")
        return pd.DataFrame()

    logger.info(f"  Downloading {symbol} via yfinance ({yf_ticker})...")

    try:
        ticker = yf.Ticker(yf_ticker)
        df = ticker.history(start=start_date, auto_adjust=True)

        if df.empty:
            logger.warning(f"  {symbol}: no data returned from yfinance")
            return pd.DataFrame()

        df = df.reset_index()

        df = df.rename(columns={
            "Date": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume_usd",
        })

        df = df[["date", "open", "high", "low", "close", "volume_usd"]].copy()

        # Ensure timezone-aware UTC
        if df["date"].dt.tz is None:
            df["date"] = df["date"].dt.tz_localize("UTC")
        else:
            df["date"] = df["date"].dt.tz_convert("UTC")

        # Compute daily percent change
        df["pct_change"] = df["close"].pct_change() * 100
        df["pct_change"] = df["pct_change"].round(4)

        # No market cap from yfinance, set to None
        df["market_cap_usd"] = None

        # Drop rows with null close
        df = df.dropna(subset=["close"])

        # Replace NaN with None
        df = df.replace({np.nan: None})

        logger.info(f"  {symbol}: {len(df)} daily records downloaded")
        return df

    except Exception as e:
        logger.warning(f"  Failed to download {symbol}: {e}")
        return pd.DataFrame()


def insert_crypto_data(crypto_id: int, df: pd.DataFrame) -> int:
    """
    Bulk insert crypto price data.
    Uses ON CONFLICT DO NOTHING to skip duplicates.
    """
    if df.empty:
        return 0

    rows = []
    for _, r in df.iterrows():
        rows.append({
            "date": r["date"],
            "crypto_id": crypto_id,
            "open": r["open"],
            "high": r["high"],
            "low": r["low"],
            "close": r["close"],
            "volume_usd": r["volume_usd"],
            "market_cap_usd": r["market_cap_usd"],
            "pct_change": r["pct_change"],
        })

    batch_size = 1000
    inserted = 0

    with engine.connect() as conn:
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            conn.execute(text("""
                INSERT INTO crypto_prices
                    (date, crypto_id, open, high, low, close, volume_usd, market_cap_usd, pct_change)
                VALUES
                    (:date, :crypto_id, :open, :high, :low, :close, :volume_usd, :market_cap_usd, :pct_change)
                ON CONFLICT DO NOTHING
            """), batch)
            inserted += len(batch)

        conn.commit()

    return inserted


def ingest_crypto(start_date: str = None):
    """
    Full crypto ingestion pipeline using yfinance.

    Args:
        start_date: Start date (default from config).
                    BTC data starts ~2014, ETH ~2017, SOL ~2020 on yfinance.
    """
    start_date = start_date or settings.data_start_date

    logger.info("=" * 55)
    logger.info("CRYPTO DATA INGESTION (yfinance)")
    logger.info(f"Date range: {start_date} → present")
    logger.info("=" * 55)

    assets = get_crypto_assets()
    total_rows = 0

    for asset in assets:
        df = download_crypto_history(
            symbol=asset["symbol"],
            start_date=start_date,
        )

        if not df.empty:
            count = insert_crypto_data(asset["id"], df)
            total_rows += count
            logger.info(f"  ✓ {asset['symbol']}: {count} rows inserted")
        else:
            logger.warning(f"  ✗ {asset['symbol']}: no data returned")

        time.sleep(1)

    logger.info("=" * 55)
    logger.info(f"CRYPTO INGESTION COMPLETE — {total_rows:,} total rows")
    logger.info("=" * 55)

    return {"rows": total_rows}


if __name__ == "__main__":
    ingest_crypto()
