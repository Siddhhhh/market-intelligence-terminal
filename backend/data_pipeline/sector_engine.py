"""
Sector Performance Engine

Precomputes daily sector performance metrics and stores them in the
sector_performance table. This eliminates expensive runtime aggregation
across 3.6M+ stock rows.

The engine:
    1. Finds all trading dates that haven't been computed yet
    2. For each date, aggregates pct_change by sector
    3. Identifies top gainer and loser per sector
    4. Stores results for instant heatmap queries

Usage:
    from backend.data_pipeline.sector_engine import compute_sector_performance
    compute_sector_performance()           # compute all missing dates
    compute_sector_performance("2024-01-15")  # compute a specific date
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text
from loguru import logger
from database.session import engine


def compute_sector_performance(target_date: str = None):
    """
    Compute sector performance for missing dates or a specific date.

    Uses a single efficient SQL query with window functions to compute
    sector averages, top gainers, and top losers in one pass.
    """
    logger.info("=" * 55)
    logger.info("SECTOR PERFORMANCE ENGINE")
    logger.info("=" * 55)

    with engine.connect() as conn:
        # Create table if it doesn't exist (handles first run)
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS sector_performance (
                date DATE NOT NULL,
                sector_id INTEGER NOT NULL REFERENCES sectors(id) ON DELETE CASCADE,
                avg_pct_change NUMERIC(8,4) NOT NULL,
                company_count INTEGER NOT NULL,
                total_volume BIGINT,
                top_gainer_ticker VARCHAR(20),
                top_gainer_pct NUMERIC(8,4),
                top_loser_ticker VARCHAR(20),
                top_loser_pct NUMERIC(8,4),
                computed_at TIMESTAMP DEFAULT NOW() NOT NULL,
                PRIMARY KEY (date, sector_id)
            )
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_sector_perf_date ON sector_performance(date)
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_sector_perf_sector_date ON sector_performance(sector_id, date)
        """))
        conn.commit()

        if target_date:
            # Compute for a specific date
            dates_to_compute = [target_date]
            logger.info(f"Computing for specific date: {target_date}")
        else:
            # Find all trading dates not yet computed
            result = conn.execute(text("""
                SELECT DISTINCT s.date::date as trading_date
                FROM stocks s
                WHERE s.pct_change IS NOT NULL
                AND s.date::date NOT IN (
                    SELECT DISTINCT date FROM sector_performance
                )
                ORDER BY trading_date
            """)).fetchall()
            dates_to_compute = [str(r[0]) for r in result]
            logger.info(f"Found {len(dates_to_compute)} dates to compute")

        if not dates_to_compute:
            logger.info("All dates already computed. Nothing to do.")
            return {"dates_computed": 0}

        # Process in batches of 100 dates
        batch_size = 100
        total_computed = 0
        start_time = time.time()

        for i in range(0, len(dates_to_compute), batch_size):
            batch = dates_to_compute[i:i + batch_size]

            for date_str in batch:
                _compute_single_date(conn, date_str)
                total_computed += 1

            conn.commit()

            if total_computed % 500 == 0 and total_computed > 0:
                elapsed = time.time() - start_time
                rate = total_computed / elapsed
                remaining = (len(dates_to_compute) - total_computed) / rate if rate > 0 else 0
                logger.info(
                    f"  Progress: {total_computed}/{len(dates_to_compute)} dates "
                    f"({rate:.0f} dates/sec, ~{remaining:.0f}s remaining)"
                )

        conn.commit()

    elapsed = time.time() - start_time
    logger.info("=" * 55)
    logger.info(f"SECTOR ENGINE COMPLETE — {total_computed} dates in {elapsed:.1f}s")
    logger.info("=" * 55)

    return {"dates_computed": total_computed}


def _compute_single_date(conn, date_str: str):
    """
    Compute sector performance for a single date using one efficient SQL query.

    Uses window functions to get top gainer and loser per sector without N+1 queries.
    """
    conn.execute(text("""
        INSERT INTO sector_performance
            (date, sector_id, avg_pct_change, company_count, total_volume,
             top_gainer_ticker, top_gainer_pct, top_loser_ticker, top_loser_pct)
        SELECT
            :date_val,
            ranked.sector_id,
            ranked.avg_pct,
            ranked.company_count,
            ranked.total_vol,
            MAX(CASE WHEN ranked.gain_rank = 1 THEN ranked.ticker END),
            MAX(CASE WHEN ranked.gain_rank = 1 THEN ranked.pct_change END),
            MAX(CASE WHEN ranked.loss_rank = 1 THEN ranked.ticker END),
            MAX(CASE WHEN ranked.loss_rank = 1 THEN ranked.pct_change END)
        FROM (
            SELECT
                c.sector_id,
                c.ticker,
                s.pct_change,
                s.volume,
                AVG(s.pct_change) OVER (PARTITION BY c.sector_id) as avg_pct,
                COUNT(*) OVER (PARTITION BY c.sector_id) as company_count,
                SUM(s.volume) OVER (PARTITION BY c.sector_id) as total_vol,
                ROW_NUMBER() OVER (PARTITION BY c.sector_id ORDER BY s.pct_change DESC) as gain_rank,
                ROW_NUMBER() OVER (PARTITION BY c.sector_id ORDER BY s.pct_change ASC) as loss_rank
            FROM stocks s
            JOIN companies c ON s.company_id = c.id
            WHERE s.date::date = :date_val
            AND s.pct_change IS NOT NULL
            AND c.sector_id IS NOT NULL
        ) ranked
        WHERE ranked.gain_rank = 1 OR ranked.loss_rank = 1
        GROUP BY ranked.sector_id, ranked.avg_pct, ranked.company_count, ranked.total_vol
        ON CONFLICT (date, sector_id) DO UPDATE SET
            avg_pct_change = EXCLUDED.avg_pct_change,
            company_count = EXCLUDED.company_count,
            total_volume = EXCLUDED.total_volume,
            top_gainer_ticker = EXCLUDED.top_gainer_ticker,
            top_gainer_pct = EXCLUDED.top_gainer_pct,
            top_loser_ticker = EXCLUDED.top_loser_ticker,
            top_loser_pct = EXCLUDED.top_loser_pct,
            computed_at = NOW()
    """), {"date_val": date_str})


if __name__ == "__main__":
    compute_sector_performance()
