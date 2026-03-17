"""
Macroeconomic Data Ingestion Pipeline

Downloads key macroeconomic indicators using the FRED API (free, no key needed
for basic CSV endpoints). Stores data in the macro_events table.

Indicators:
    - Federal Funds Rate (DFF)
    - Consumer Price Index (CPIAUCSL)
    - GDP Growth Rate (A191RL1Q225SBEA)
    - Unemployment Rate (UNRATE)
    - 10-Year Treasury Yield (DGS10)
    - VIX Volatility Index (VIXCLS)

FRED provides free CSV downloads without an API key via:
    https://fred.stlouisfed.org/graph/fredgraph.csv?id=SERIES_ID

Usage:
    from backend.data_pipeline.macro import ingest_macro
    ingest_macro()
"""

import sys
import os
import time
from datetime import datetime, timezone

import pandas as pd
import numpy as np
import httpx
from sqlalchemy import text
from loguru import logger

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import settings
from database.session import engine


# ── Indicator Definitions ───────────────────────────────────

INDICATORS = [
    {
        "fred_id": "DFF",
        "name": "fed_funds_rate",
        "description": "Federal Funds Effective Rate (daily)",
    },
    {
        "fred_id": "CPIAUCSL",
        "name": "cpi",
        "description": "Consumer Price Index for All Urban Consumers (monthly)",
    },
    {
        "fred_id": "A191RL1Q225SBEA",
        "name": "gdp_growth",
        "description": "Real GDP Growth Rate (quarterly, annualized)",
    },
    {
        "fred_id": "UNRATE",
        "name": "unemployment_rate",
        "description": "Civilian Unemployment Rate (monthly)",
    },
    {
        "fred_id": "DGS10",
        "name": "treasury_10y",
        "description": "10-Year Treasury Constant Maturity Rate (daily)",
    },
    {
        "fred_id": "VIXCLS",
        "name": "vix",
        "description": "CBOE Volatility Index VIX (daily)",
    },
]


def download_fred_series(
    fred_id: str,
    start_date: str,
    request_delay: float = 2.0,
) -> pd.DataFrame:
    """
    Download a single FRED series as CSV.

    The free CSV endpoint does not require an API key:
        https://fred.stlouisfed.org/graph/fredgraph.csv?id=DFF&cosd=1990-01-01

    Returns a DataFrame with columns: date, value
    """
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv"
    params = {
        "id": fred_id,
        "cosd": start_date,
    }

    try:
        resp = httpx.get(url, params=params, timeout=30.0, follow_redirects=True)

        if resp.status_code != 200:
            logger.warning(f"    FRED returned {resp.status_code} for {fred_id}")
            return pd.DataFrame()

        # Parse CSV from response text
        from io import StringIO
        df = pd.read_csv(StringIO(resp.text))

        if df.empty:
            return pd.DataFrame()

        # FRED CSV columns are: DATE, SERIES_ID
        df.columns = ["date", "value"]

        # Convert date
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])

        # Make timezone-aware
        df["date"] = df["date"].dt.tz_localize("UTC")

        # FRED uses "." for missing values
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df = df.dropna(subset=["value"])

        # Compute change from previous value
        df["previous_value"] = df["value"].shift(1)
        df["change_pct"] = ((df["value"] - df["previous_value"]) / df["previous_value"].abs()) * 100
        df["change_pct"] = df["change_pct"].round(4)

        # Replace NaN
        df = df.replace({np.nan: None})

        return df

    except Exception as e:
        logger.warning(f"    Error downloading FRED series {fred_id}: {e}")
        return pd.DataFrame()


def insert_macro_data(indicator_name: str, description: str, df: pd.DataFrame) -> int:
    """
    Bulk insert macro data into macro_events table.
    Uses ON CONFLICT on (date, indicator) to skip duplicates.
    """
    if df.empty:
        return 0

    rows = []
    for _, r in df.iterrows():
        rows.append({
            "date": r["date"],
            "indicator": indicator_name,
            "value": r["value"],
            "previous_value": r["previous_value"],
            "change_pct": r["change_pct"],
            "source": "FRED",
            "description": description,
        })

    batch_size = 500
    inserted = 0

    with engine.connect() as conn:
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            conn.execute(text("""
                INSERT INTO macro_events
                    (date, indicator, value, previous_value, change_pct, source, description)
                VALUES
                    (:date, :indicator, :value, :previous_value, :change_pct, :source, :description)
                ON CONFLICT ON CONSTRAINT uq_macro_date_indicator DO NOTHING
            """), batch)
            inserted += len(batch)

        conn.commit()

    return inserted


def ingest_macro(start_date: str = None, request_delay: float = 2.0):
    """
    Full macro data ingestion pipeline.

    Args:
        start_date: Start date for data (default from config)
        request_delay: Seconds between FRED API requests
    """
    start_date = start_date or settings.data_start_date

    logger.info("=" * 55)
    logger.info("MACRO DATA INGESTION (FRED)")
    logger.info(f"Date range: {start_date} → present")
    logger.info("=" * 55)

    total_rows = 0

    for indicator in INDICATORS:
        logger.info(f"Downloading {indicator['name']} ({indicator['fred_id']})...")

        df = download_fred_series(
            fred_id=indicator["fred_id"],
            start_date=start_date,
            request_delay=request_delay,
        )

        if not df.empty:
            count = insert_macro_data(
                indicator_name=indicator["name"],
                description=indicator["description"],
                df=df,
            )
            total_rows += count
            logger.info(f"  ✓ {indicator['name']}: {count} rows inserted")
        else:
            logger.warning(f"  ✗ {indicator['name']}: no data returned")

        time.sleep(request_delay)

    logger.info("=" * 55)
    logger.info(f"MACRO INGESTION COMPLETE — {total_rows:,} total rows")
    logger.info("=" * 55)

    return {"rows": total_rows}


if __name__ == "__main__":
    ingest_macro()
