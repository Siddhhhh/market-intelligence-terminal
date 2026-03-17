"""
Stock Data Ingestion Pipeline

Downloads historical OHLCV data for S&P 500 companies using yfinance.
Cleans, validates, computes percent change, and bulk-inserts into the
stocks hypertable.

Features:
    - Fetches current S&P 500 ticker list from Wikipedia
    - Downloads 35+ years of daily price data (1990-present)
    - Batched inserts (1000 rows at a time) for performance
    - ON CONFLICT DO NOTHING to avoid duplicates on re-runs
    - Progress bars via tqdm
    - Automatic sector mapping from yfinance metadata

Usage:
    from backend.data_pipeline.stocks import ingest_sp500
    ingest_sp500()
"""

import sys
import os
import time
from datetime import datetime, timezone

import pandas as pd
import numpy as np
import yfinance as yf
from sqlalchemy import text
from loguru import logger
from tqdm import tqdm

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import settings
from database.session import engine


# ── S&P 500 Ticker List ────────────────────────────────────

# Sector mapping from yfinance sector names to our database sector keys
SECTOR_MAP = {
    "Technology": "technology",
    "Information Technology": "technology",
    "Healthcare": "healthcare",
    "Health Care": "healthcare",
    "Financial Services": "financials",
    "Financials": "financials",
    "Consumer Cyclical": "consumer_discretionary",
    "Consumer Discretionary": "consumer_discretionary",
    "Consumer Defensive": "consumer_staples",
    "Consumer Staples": "consumer_staples",
    "Energy": "energy",
    "Industrials": "industrials",
    "Basic Materials": "materials",
    "Materials": "materials",
    "Utilities": "utilities",
    "Real Estate": "real_estate",
    "Communication Services": "communication_services",
}


def get_sp500_tickers() -> pd.DataFrame:
    """
    Fetch the current S&P 500 company list.

    Primary source: DataHub.io open data CSV (no auth, no scraping)
    Fallback: hardcoded top 30 tickers

    Returns:
        DataFrame with columns: ticker, name, sector, industry
    """
    logger.info("Fetching S&P 500 ticker list...")

    # Source 1: DataHub.io (open data, reliable, updated regularly)
    try:
        import httpx
        url = "https://datahub.io/core/s-and-p-500-companies/_r/-/data/constituents.csv"
        resp = httpx.get(url, timeout=15.0, follow_redirects=True)
        resp.raise_for_status()

        from io import StringIO
        df = pd.read_csv(StringIO(resp.text))

        df = df.rename(columns={
            "Symbol": "ticker",
            "Security": "name",
            "GICS Sector": "sector",
            "GICS Sub-Industry": "industry",
        })

        # Clean tickers (BRK.B → BRK-B for yfinance)
        df["ticker"] = df["ticker"].str.replace(".", "-", regex=False)

        logger.info(f"  Found {len(df)} S&P 500 companies (DataHub)")
        return df[["ticker", "name", "sector", "industry"]].copy()

    except Exception as e:
        logger.warning(f"DataHub fetch failed: {e}")

    # Source 2: Wikipedia (backup)
    try:
        import httpx
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = httpx.get(url, headers=headers, timeout=15.0, follow_redirects=True)
        resp.raise_for_status()

        from io import StringIO
        tables = pd.read_html(StringIO(resp.text), header=0)
        df = tables[0]

        df = df.rename(columns={
            "Symbol": "ticker",
            "Security": "name",
            "GICS Sector": "sector",
            "GICS Sub-Industry": "industry",
        })

        df["ticker"] = df["ticker"].str.replace(".", "-", regex=False)
        logger.info(f"  Found {len(df)} S&P 500 companies (Wikipedia)")
        return df[["ticker", "name", "sector", "industry"]].copy()

    except Exception as e:
        logger.error(f"Wikipedia fetch also failed: {e}")
        logger.info("Falling back to a minimal set of tickers...")
        # Fallback: top 30 tickers if Wikipedia fails
        fallback = [
            ("AAPL", "Apple Inc.", "Technology", "Technology Hardware"),
            ("MSFT", "Microsoft Corp.", "Technology", "Systems Software"),
            ("AMZN", "Amazon.com Inc.", "Consumer Discretionary", "Internet Retail"),
            ("NVDA", "NVIDIA Corp.", "Technology", "Semiconductors"),
            ("GOOGL", "Alphabet Inc.", "Communication Services", "Interactive Media"),
            ("META", "Meta Platforms Inc.", "Communication Services", "Interactive Media"),
            ("TSLA", "Tesla Inc.", "Consumer Discretionary", "Auto Manufacturers"),
            ("BRK-B", "Berkshire Hathaway", "Financials", "Insurance"),
            ("JPM", "JPMorgan Chase", "Financials", "Banks"),
            ("V", "Visa Inc.", "Financials", "Financial Services"),
            ("JNJ", "Johnson & Johnson", "Healthcare", "Pharmaceuticals"),
            ("UNH", "UnitedHealth Group", "Healthcare", "Managed Healthcare"),
            ("XOM", "Exxon Mobil", "Energy", "Oil & Gas"),
            ("MA", "Mastercard", "Financials", "Financial Services"),
            ("PG", "Procter & Gamble", "Consumer Staples", "Household Products"),
            ("HD", "Home Depot", "Consumer Discretionary", "Home Improvement"),
            ("CVX", "Chevron", "Energy", "Oil & Gas"),
            ("LLY", "Eli Lilly", "Healthcare", "Pharmaceuticals"),
            ("ABBV", "AbbVie Inc.", "Healthcare", "Biotechnology"),
            ("PFE", "Pfizer Inc.", "Healthcare", "Pharmaceuticals"),
            ("COST", "Costco", "Consumer Staples", "Discount Stores"),
            ("KO", "Coca-Cola", "Consumer Staples", "Beverages"),
            ("PEP", "PepsiCo", "Consumer Staples", "Beverages"),
            ("WMT", "Walmart", "Consumer Staples", "Discount Stores"),
            ("BAC", "Bank of America", "Financials", "Banks"),
            ("DIS", "Walt Disney", "Communication Services", "Entertainment"),
            ("NFLX", "Netflix", "Communication Services", "Entertainment"),
            ("AMD", "AMD", "Technology", "Semiconductors"),
            ("INTC", "Intel Corp.", "Technology", "Semiconductors"),
            ("CRM", "Salesforce", "Technology", "Application Software"),
        ]
        return pd.DataFrame(fallback, columns=["ticker", "name", "sector", "industry"])


def upsert_companies(tickers_df: pd.DataFrame) -> dict:
    """
    Insert or update companies in the database.
    Returns a dict mapping ticker → company_id.
    """
    logger.info("Upserting companies into database...")

    ticker_to_id = {}

    with engine.connect() as conn:
        # Get sector_id mapping
        rows = conn.execute(text("SELECT id, name FROM sectors")).fetchall()
        sector_ids = {r[1]: r[0] for r in rows}

        for _, row in tickers_df.iterrows():
            sector_key = SECTOR_MAP.get(row["sector"], "technology")
            sector_id = sector_ids.get(sector_key)

            conn.execute(text("""
                INSERT INTO companies (ticker, name, sector_id, industry, is_sp500, is_active)
                VALUES (:ticker, :name, :sector_id, :industry, TRUE, TRUE)
                ON CONFLICT (ticker) DO UPDATE SET
                    name = EXCLUDED.name,
                    sector_id = EXCLUDED.sector_id,
                    industry = EXCLUDED.industry,
                    is_sp500 = TRUE
            """), {
                "ticker": row["ticker"],
                "name": row["name"],
                "sector_id": sector_id,
                "industry": row.get("industry", None),
            })

        conn.commit()

        # Fetch all company IDs
        rows = conn.execute(text("SELECT id, ticker FROM companies")).fetchall()
        ticker_to_id = {r[1]: r[0] for r in rows}

    logger.info(f"  {len(ticker_to_id)} companies in database")
    return ticker_to_id


def download_stock_history(ticker: str, start_date: str) -> pd.DataFrame:
    """
    Download historical OHLCV data for a single ticker using yfinance.

    Returns a cleaned DataFrame or empty DataFrame on failure.
    """
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(start=start_date, auto_adjust=True)

        if df.empty:
            return pd.DataFrame()

        # Reset index so Date becomes a column
        df = df.reset_index()

        # Rename columns to match our schema
        df = df.rename(columns={
            "Date": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        })

        # Keep only the columns we need
        df = df[["date", "open", "high", "low", "close", "volume"]].copy()

        # Ensure date is timezone-aware UTC
        if df["date"].dt.tz is None:
            df["date"] = df["date"].dt.tz_localize("UTC")
        else:
            df["date"] = df["date"].dt.tz_convert("UTC")

        # Compute daily percent change
        df["pct_change"] = df["close"].pct_change() * 100
        df["pct_change"] = df["pct_change"].round(4)

        # Drop rows with NaN (first row has no pct_change)
        df = df.dropna(subset=["close"])

        # Replace remaining NaN with None for database compatibility
        df = df.replace({np.nan: None})

        return df

    except Exception as e:
        logger.warning(f"  Failed to download {ticker}: {e}")
        return pd.DataFrame()


def insert_stock_data(ticker: str, company_id: int, df: pd.DataFrame) -> int:
    """
    Bulk insert stock data for one company.
    Uses ON CONFLICT DO NOTHING to skip duplicates.
    Returns the number of rows inserted.
    """
    if df.empty:
        return 0

    rows = []
    for _, r in df.iterrows():
        rows.append({
            "date": r["date"],
            "company_id": company_id,
            "open": r["open"],
            "high": r["high"],
            "low": r["low"],
            "close": r["close"],
            "volume": int(r["volume"]) if r["volume"] is not None else None,
            "pct_change": r["pct_change"],
        })

    # Batch insert in chunks of 1000
    inserted = 0
    batch_size = 1000

    with engine.connect() as conn:
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            conn.execute(text("""
                INSERT INTO stocks (date, company_id, open, high, low, close, volume, pct_change)
                VALUES (:date, :company_id, :open, :high, :low, :close, :volume, :pct_change)
                ON CONFLICT DO NOTHING
            """), batch)
            inserted += len(batch)

        conn.commit()

    return inserted


def ingest_sp500(start_date: str = None, batch_delay: float = 0.5):
    """
    Full S&P 500 ingestion pipeline.

    Args:
        start_date: Start date for historical data (default from config)
        batch_delay: Seconds to wait between tickers to avoid rate limits
    """
    start_date = start_date or settings.data_start_date

    logger.info("=" * 55)
    logger.info("STOCK DATA INGESTION — S&P 500")
    logger.info(f"Date range: {start_date} → present")
    logger.info("=" * 55)

    # Step 1: Get ticker list
    tickers_df = get_sp500_tickers()

    # Step 2: Upsert companies
    ticker_to_id = upsert_companies(tickers_df)

    # Step 3: Download and insert data for each ticker
    total_rows = 0
    success_count = 0
    fail_count = 0
    tickers = tickers_df["ticker"].tolist()

    logger.info(f"Downloading historical data for {len(tickers)} companies...")

    for ticker in tqdm(tickers, desc="Downloading stocks", unit="company"):
        company_id = ticker_to_id.get(ticker)
        if not company_id:
            fail_count += 1
            continue

        df = download_stock_history(ticker, start_date)

        if not df.empty:
            count = insert_stock_data(ticker, company_id, df)
            total_rows += count
            success_count += 1
        else:
            fail_count += 1

        # Rate limit protection
        time.sleep(batch_delay)

    logger.info("=" * 55)
    logger.info(f"STOCK INGESTION COMPLETE")
    logger.info(f"  Companies succeeded: {success_count}")
    logger.info(f"  Companies failed:    {fail_count}")
    logger.info(f"  Total rows inserted: {total_rows:,}")
    logger.info("=" * 55)

    return {"success": success_count, "failed": fail_count, "rows": total_rows}


if __name__ == "__main__":
    ingest_sp500()
