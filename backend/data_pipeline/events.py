"""
Market Event Detection Engine

Scans the stocks and crypto_prices tables for anomalies and stores
detected events in the market_events table.

Detection rules:
    1. price_spike    — single stock/crypto rose > 8% in one day
    2. price_crash    — single stock/crypto fell > 8% in one day
    3. volume_anomaly — volume > 3x the 20-day rolling average
    4. sector_move    — 5+ companies in same sector move > 3% same direction
    5. market_crash   — 20+ companies drop > 5% on the same day

Usage:
    from backend.data_pipeline.events import detect_all_events
    detect_all_events()
"""

import sys
import os
from datetime import datetime, timezone

from sqlalchemy import text
from loguru import logger

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from database.session import engine


def detect_price_spikes_and_crashes():
    """
    Detect stocks and crypto with daily moves > 8%.
    Inserts price_spike and price_crash events.
    """
    logger.info("  Detecting price spikes and crashes (> 8%)...")

    with engine.connect() as conn:
        # Stock spikes and crashes
        result = conn.execute(text("""
            INSERT INTO market_events (date, event_type, severity, entity_type, entity_id, ticker, magnitude, description)
            SELECT
                s.date,
                CASE WHEN s.pct_change > 0 THEN 'price_spike' ELSE 'price_crash' END,
                CASE
                    WHEN ABS(s.pct_change) > 20 THEN 'critical'
                    WHEN ABS(s.pct_change) > 15 THEN 'high'
                    WHEN ABS(s.pct_change) > 10 THEN 'medium'
                    ELSE 'low'
                END,
                'stock',
                s.company_id,
                c.ticker,
                s.pct_change,
                c.ticker || ' moved ' || ROUND(s.pct_change::numeric, 2) || '% on ' || s.date::date
            FROM stocks s
            JOIN companies c ON s.company_id = c.id
            WHERE ABS(s.pct_change) > 8
            AND NOT EXISTS (
                SELECT 1 FROM market_events me
                WHERE me.date = s.date
                AND me.entity_type = 'stock'
                AND me.entity_id = s.company_id
                AND me.event_type IN ('price_spike', 'price_crash')
            )
        """))
        stock_events = result.rowcount
        conn.commit()

    with engine.connect() as conn:
        # Crypto spikes and crashes
        result = conn.execute(text("""
            INSERT INTO market_events (date, event_type, severity, entity_type, entity_id, ticker, magnitude, description)
            SELECT
                cp.date,
                CASE WHEN cp.pct_change > 0 THEN 'price_spike' ELSE 'price_crash' END,
                CASE
                    WHEN ABS(cp.pct_change) > 20 THEN 'critical'
                    WHEN ABS(cp.pct_change) > 15 THEN 'high'
                    WHEN ABS(cp.pct_change) > 10 THEN 'medium'
                    ELSE 'low'
                END,
                'crypto',
                cp.crypto_id,
                ca.symbol,
                cp.pct_change,
                ca.symbol || ' moved ' || ROUND(cp.pct_change::numeric, 2) || '% on ' || cp.date::date
            FROM crypto_prices cp
            JOIN crypto_assets ca ON cp.crypto_id = ca.id
            WHERE ABS(cp.pct_change) > 8
            AND NOT EXISTS (
                SELECT 1 FROM market_events me
                WHERE me.date = cp.date
                AND me.entity_type = 'crypto'
                AND me.entity_id = cp.crypto_id
                AND me.event_type IN ('price_spike', 'price_crash')
            )
        """))
        crypto_events = result.rowcount
        conn.commit()

    total = stock_events + crypto_events
    logger.info(f"    ✓ {stock_events} stock events, {crypto_events} crypto events ({total} total)")
    return total


def detect_market_crashes():
    """
    Detect days where 20+ companies dropped > 5%.
    These are market-wide crash events.
    """
    logger.info("  Detecting market-wide crashes (20+ companies down > 5%)...")

    with engine.connect() as conn:
        result = conn.execute(text("""
            INSERT INTO market_events (date, event_type, severity, entity_type, magnitude, description, metadata)
            SELECT
                s.date,
                'market_crash',
                CASE
                    WHEN COUNT(*) > 100 THEN 'critical'
                    WHEN COUNT(*) > 50 THEN 'high'
                    ELSE 'medium'
                END,
                'stock',
                ROUND(AVG(s.pct_change)::numeric, 2),
                COUNT(*) || ' companies dropped > 5% on ' || s.date::date,
                json_build_object(
                    'companies_affected', COUNT(*),
                    'avg_drop', ROUND(AVG(s.pct_change)::numeric, 2)
                )
            FROM stocks s
            WHERE s.pct_change < -5
            GROUP BY s.date
            HAVING COUNT(*) >= 20
            AND NOT EXISTS (
                SELECT 1 FROM market_events me
                WHERE me.date = s.date
                AND me.event_type = 'market_crash'
            )
        """))
        count = result.rowcount
        conn.commit()

    logger.info(f"    ✓ {count} market crash events detected")
    return count


def detect_sector_moves():
    """
    Detect days where 5+ companies in the same sector move > 3% in the same direction.
    """
    logger.info("  Detecting sector-wide movements (5+ companies > 3%)...")

    with engine.connect() as conn:
        # Positive sector moves
        result_up = conn.execute(text("""
            INSERT INTO market_events (date, event_type, severity, entity_type, magnitude, description, metadata)
            SELECT
                s.date,
                'sector_move',
                'medium',
                'stock',
                ROUND(AVG(s.pct_change)::numeric, 2),
                sec.display_name || ': ' || COUNT(*) || ' companies rose > 3% on ' || s.date::date,
                json_build_object(
                    'sector', sec.name,
                    'direction', 'up',
                    'companies_count', COUNT(*),
                    'avg_move', ROUND(AVG(s.pct_change)::numeric, 2)
                )
            FROM stocks s
            JOIN companies c ON s.company_id = c.id
            JOIN sectors sec ON c.sector_id = sec.id
            WHERE s.pct_change > 3
            GROUP BY s.date, sec.id, sec.name, sec.display_name
            HAVING COUNT(*) >= 5
            AND NOT EXISTS (
                SELECT 1 FROM market_events me
                WHERE me.date = s.date
                AND me.event_type = 'sector_move'
                AND me.metadata->>'sector' = sec.name
                AND me.metadata->>'direction' = 'up'
            )
        """))
        up_count = result_up.rowcount
        conn.commit()

    with engine.connect() as conn:
        # Negative sector moves
        result_down = conn.execute(text("""
            INSERT INTO market_events (date, event_type, severity, entity_type, magnitude, description, metadata)
            SELECT
                s.date,
                'sector_move',
                'medium',
                'stock',
                ROUND(AVG(s.pct_change)::numeric, 2),
                sec.display_name || ': ' || COUNT(*) || ' companies fell > 3% on ' || s.date::date,
                json_build_object(
                    'sector', sec.name,
                    'direction', 'down',
                    'companies_count', COUNT(*),
                    'avg_move', ROUND(AVG(s.pct_change)::numeric, 2)
                )
            FROM stocks s
            JOIN companies c ON s.company_id = c.id
            JOIN sectors sec ON c.sector_id = sec.id
            WHERE s.pct_change < -3
            GROUP BY s.date, sec.id, sec.name, sec.display_name
            HAVING COUNT(*) >= 5
            AND NOT EXISTS (
                SELECT 1 FROM market_events me
                WHERE me.date = s.date
                AND me.event_type = 'sector_move'
                AND me.metadata->>'sector' = sec.name
                AND me.metadata->>'direction' = 'down'
            )
        """))
        down_count = result_down.rowcount
        conn.commit()

    total = up_count + down_count
    logger.info(f"    ✓ {up_count} sector rallies, {down_count} sector selloffs ({total} total)")
    return total


def detect_all_events():
    """Run all event detection rules."""
    logger.info("=" * 55)
    logger.info("MARKET EVENT DETECTION")
    logger.info("=" * 55)

    total = 0
    total += detect_price_spikes_and_crashes()
    total += detect_market_crashes()
    total += detect_sector_moves()

    with engine.connect() as conn:
        event_count = conn.execute(text("SELECT COUNT(*) FROM market_events")).scalar()

    logger.info("=" * 55)
    logger.info(f"EVENT DETECTION COMPLETE — {total} new events detected")
    logger.info(f"Total events in database: {event_count:,}")
    logger.info("=" * 55)

    return {"new_events": total, "total_events": event_count}


if __name__ == "__main__":
    detect_all_events()
