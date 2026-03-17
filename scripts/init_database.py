"""
Market Intelligence Terminal — Database Initialization

This script:
    1. Creates all tables defined in database/models.py
    2. Converts stocks and crypto_prices to TimescaleDB hypertables
    3. Seeds the sectors table with GICS sectors
    4. Seeds the crypto_assets table with BTC, ETH, SOL

Run from project root:
    python scripts/init_database.py

This is idempotent — safe to run multiple times.
"""

import sys
import os

# Add project root to path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text, inspect
from database.models import Base
from database.session import engine
from loguru import logger


# ── GICS Sector Definitions ────────────────────────────────

SECTORS = [
    {"name": "technology", "display_name": "Technology"},
    {"name": "healthcare", "display_name": "Healthcare"},
    {"name": "financials", "display_name": "Financials"},
    {"name": "consumer_discretionary", "display_name": "Consumer Discretionary"},
    {"name": "consumer_staples", "display_name": "Consumer Staples"},
    {"name": "energy", "display_name": "Energy"},
    {"name": "industrials", "display_name": "Industrials"},
    {"name": "materials", "display_name": "Materials"},
    {"name": "utilities", "display_name": "Utilities"},
    {"name": "real_estate", "display_name": "Real Estate"},
    {"name": "communication_services", "display_name": "Communication Services"},
]


# ── Crypto Asset Definitions ───────────────────────────────

CRYPTO_ASSETS = [
    {"symbol": "BTC", "name": "Bitcoin", "coingecko_id": "bitcoin"},
    {"symbol": "ETH", "name": "Ethereum", "coingecko_id": "ethereum"},
    {"symbol": "SOL", "name": "Solana", "coingecko_id": "solana"},
]


def create_tables():
    """Create all tables from SQLAlchemy models."""
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("All tables created.")


def create_hypertables():
    """
    Convert stocks and crypto_prices to TimescaleDB hypertables.

    Hypertables partition data by time automatically.
    This makes queries like "show AAPL from 2020 to 2023" extremely fast
    even with millions of rows.

    Uses the classic create_hypertable(table, column) syntax
    which works with all TimescaleDB versions.
    """
    logger.info("Converting time-series tables to TimescaleDB hypertables...")

    with engine.connect() as conn:
        # Check if TimescaleDB is available
        result = conn.execute(
            text("SELECT extversion FROM pg_extension WHERE extname = 'timescaledb'")
        ).fetchone()

        if not result:
            logger.warning(
                "TimescaleDB extension not found. "
                "Tables will work but without time-series optimization. "
                "Run: CREATE EXTENSION timescaledb; in your database."
            )
            return

        logger.info(f"TimescaleDB v{result[0]} detected.")

        # Convert stocks to hypertable
        try:
            conn.execute(text("""
                SELECT create_hypertable(
                    'stocks',
                    'date',
                    chunk_time_interval => INTERVAL '365 days',
                    if_not_exists => TRUE,
                    migrate_data => TRUE
                );
            """))
            conn.commit()
            logger.info("  ✓ stocks → hypertable (365-day chunks)")
        except Exception as e:
            conn.rollback()
            if "already a hypertable" in str(e).lower():
                logger.info("  ✓ stocks is already a hypertable")
            else:
                logger.error(f"  ✗ stocks hypertable failed: {e}")

        # Convert crypto_prices to hypertable
        try:
            conn.execute(text("""
                SELECT create_hypertable(
                    'crypto_prices',
                    'date',
                    chunk_time_interval => INTERVAL '365 days',
                    if_not_exists => TRUE,
                    migrate_data => TRUE
                );
            """))
            conn.commit()
            logger.info("  ✓ crypto_prices → hypertable (365-day chunks)")
        except Exception as e:
            conn.rollback()
            if "already a hypertable" in str(e).lower():
                logger.info("  ✓ crypto_prices is already a hypertable")
            else:
                logger.error(f"  ✗ crypto_prices hypertable failed: {e}")

    logger.info("Hypertable setup complete.")


def seed_sectors():
    """Insert GICS sectors if they don't exist."""
    logger.info("Seeding sectors...")

    with engine.connect() as conn:
        for sector in SECTORS:
            conn.execute(text("""
                INSERT INTO sectors (name, display_name)
                VALUES (:name, :display_name)
                ON CONFLICT (name) DO NOTHING
            """), sector)

        conn.commit()

    with engine.connect() as conn:
        count_result = conn.execute(text("SELECT COUNT(*) FROM sectors")).scalar()
    logger.info(f"  ✓ {count_result} sectors in database")


def seed_crypto_assets():
    """Insert crypto asset definitions if they don't exist."""
    logger.info("Seeding crypto assets...")

    with engine.connect() as conn:
        for asset in CRYPTO_ASSETS:
            conn.execute(text("""
                INSERT INTO crypto_assets (symbol, name, coingecko_id)
                VALUES (:symbol, :name, :coingecko_id)
                ON CONFLICT (symbol) DO NOTHING
            """), asset)

        conn.commit()

    with engine.connect() as conn:
        count_result = conn.execute(text("SELECT COUNT(*) FROM crypto_assets")).scalar()
    logger.info(f"  ✓ {count_result} crypto assets in database")


def verify_schema():
    """Print a summary of all tables and their row counts."""
    logger.info("Verifying database schema...")

    inspector = inspect(engine)
    tables = inspector.get_table_names()

    print("\n" + "=" * 55)
    print("  DATABASE SCHEMA VERIFICATION")
    print("=" * 55)

    expected_tables = [
        "sectors",
        "companies",
        "stocks",
        "crypto_assets",
        "crypto_prices",
        "market_events",
        "macro_events",
        "market_regimes",
    ]

    with engine.connect() as conn:
        for table_name in expected_tables:
            if table_name in tables:
                count = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
                # Check if it's a hypertable
                is_hyper = conn.execute(text("""
                    SELECT COUNT(*) FROM timescaledb_information.hypertables
                    WHERE hypertable_name = :name
                """), {"name": table_name}).scalar()
                hyper_tag = " [HYPERTABLE]" if is_hyper else ""
                print(f"  ✓  {table_name:<20} {count:>6} rows{hyper_tag}")
            else:
                print(f"  ✗  {table_name:<20} MISSING")

    # Show columns for key tables
    print("\n" + "-" * 55)
    print("  KEY TABLE COLUMNS")
    print("-" * 55)

    for table_name in ["companies", "stocks", "crypto_prices"]:
        if table_name in tables:
            columns = inspector.get_columns(table_name)
            col_names = [c["name"] for c in columns]
            print(f"\n  {table_name}: {', '.join(col_names)}")

    print("\n" + "=" * 55)
    print("  SCHEMA VERIFICATION COMPLETE")
    print("=" * 55 + "\n")


def main():
    """Run the full database initialization."""
    print()
    logger.info("=" * 55)
    logger.info("MARKET INTELLIGENCE TERMINAL — DATABASE INIT")
    logger.info("=" * 55)

    try:
        create_tables()
        create_hypertables()
        seed_sectors()
        seed_crypto_assets()
        verify_schema()
        logger.info("Database initialization complete!")

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise


if __name__ == "__main__":
    main()
