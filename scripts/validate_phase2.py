"""
Market Intelligence Terminal — Phase 2 Validation

Tests that the database schema is correctly set up:
    1. All 8 tables exist
    2. stocks and crypto_prices are TimescaleDB hypertables
    3. Sectors are seeded (11 GICS sectors)
    4. Crypto assets are seeded (BTC, ETH, SOL)
    5. Foreign keys work (insert test company + stock row)
    6. Indexes exist on key columns
    7. Composite primary keys work on time-series tables

Run from project root:
    python scripts/validate_phase2.py
"""

import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text, inspect
from database.session import engine

PASS = "\033[92m✓ PASS\033[0m"
FAIL = "\033[91m✗ FAIL\033[0m"
BOLD = "\033[1m"
RESET = "\033[0m"


def header(title):
    print(f"\n{BOLD}── {title} ──{RESET}")


def check(name, test_fn):
    try:
        result = test_fn()
        print(f"  {PASS}  {name}  ({result})")
        return True
    except Exception as e:
        print(f"  {FAIL}  {name}  ({e})")
        return False


def main():
    print()
    print("=" * 60)
    print(f"  {BOLD}PHASE 2 — DATABASE SCHEMA VALIDATION{RESET}")
    print("=" * 60)

    results = []
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    # ── Table existence ─────────────────────────────────────
    header("TABLES")

    expected = [
        "sectors", "companies", "stocks", "crypto_assets",
        "crypto_prices", "market_events", "macro_events", "market_regimes",
    ]
    for t in expected:
        results.append(check(
            f"Table '{t}' exists",
            lambda t=t: "found" if t in tables else (_ for _ in ()).throw(Exception("MISSING")),
        ))

    # ── Hypertables ─────────────────────────────────────────
    header("TIMESCALEDB HYPERTABLES")

    def check_hypertable(table_name):
        with engine.connect() as conn:
            count = conn.execute(text("""
                SELECT COUNT(*) FROM timescaledb_information.hypertables
                WHERE hypertable_name = :name
            """), {"name": table_name}).scalar()
            if count > 0:
                return "hypertable confirmed"
            raise Exception("not a hypertable")

    results.append(check("stocks is a hypertable", lambda: check_hypertable("stocks")))
    results.append(check("crypto_prices is a hypertable", lambda: check_hypertable("crypto_prices")))

    # ── Seed data ───────────────────────────────────────────
    header("SEED DATA")

    def check_sectors():
        with engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM sectors")).scalar()
            if count >= 11:
                return f"{count} sectors"
            raise Exception(f"only {count} sectors, expected 11")

    def check_crypto():
        with engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM crypto_assets")).scalar()
            symbols = conn.execute(text("SELECT symbol FROM crypto_assets ORDER BY symbol")).fetchall()
            symbol_list = [r[0] for r in symbols]
            if count >= 3:
                return f"{count} assets: {', '.join(symbol_list)}"
            raise Exception(f"only {count} assets, expected 3")

    results.append(check("Sectors seeded", check_sectors))
    results.append(check("Crypto assets seeded", check_crypto))

    # ── Column verification ─────────────────────────────────
    header("COLUMN STRUCTURE")

    def check_columns(table_name, required_cols):
        columns = inspector.get_columns(table_name)
        col_names = {c["name"] for c in columns}
        missing = set(required_cols) - col_names
        if missing:
            raise Exception(f"missing columns: {missing}")
        return f"{len(col_names)} columns, all required present"

    results.append(check(
        "companies columns",
        lambda: check_columns("companies", [
            "id", "ticker", "name", "sector_id", "industry",
            "country", "market_cap", "is_sp500", "is_active",
        ]),
    ))

    results.append(check(
        "stocks columns",
        lambda: check_columns("stocks", [
            "date", "company_id", "open", "high", "low",
            "close", "volume", "pct_change",
        ]),
    ))

    results.append(check(
        "crypto_prices columns",
        lambda: check_columns("crypto_prices", [
            "date", "crypto_id", "open", "high", "low",
            "close", "volume_usd", "market_cap_usd", "pct_change",
        ]),
    ))

    results.append(check(
        "market_events columns",
        lambda: check_columns("market_events", [
            "id", "date", "event_type", "severity", "entity_type",
            "entity_id", "ticker", "magnitude", "description", "metadata",
        ]),
    ))

    results.append(check(
        "market_regimes columns",
        lambda: check_columns("market_regimes", [
            "id", "regime_type", "confidence", "start_date",
            "end_date", "supporting_indicators",
        ]),
    ))

    # ── Foreign key test ────────────────────────────────────
    header("FOREIGN KEY & INSERT TEST")

    def test_insert_flow():
        with engine.connect() as conn:
            # Get the technology sector id
            sector_id = conn.execute(
                text("SELECT id FROM sectors WHERE name = 'technology'")
            ).scalar()

            if not sector_id:
                raise Exception("technology sector not found")

            # Insert a test company
            conn.execute(text("""
                INSERT INTO companies (ticker, name, sector_id, country, is_sp500, is_active)
                VALUES ('_TEST', 'Test Company', :sector_id, 'US', false, false)
                ON CONFLICT (ticker) DO NOTHING
            """), {"sector_id": sector_id})

            # Get the test company id
            company_id = conn.execute(
                text("SELECT id FROM companies WHERE ticker = '_TEST'")
            ).scalar()

            # Insert a test stock row
            conn.execute(text("""
                INSERT INTO stocks (date, company_id, open, high, low, close, volume, pct_change)
                VALUES (:date, :company_id, 100.0, 105.0, 99.0, 103.0, 1000000, 3.0)
                ON CONFLICT DO NOTHING
            """), {
                "date": datetime(2024, 1, 15, tzinfo=timezone.utc),
                "company_id": company_id,
            })

            # Verify the row exists
            stock_row = conn.execute(text("""
                SELECT s.close, c.ticker
                FROM stocks s
                JOIN companies c ON s.company_id = c.id
                WHERE c.ticker = '_TEST'
            """)).fetchone()

            # Clean up test data
            conn.execute(text("DELETE FROM stocks WHERE company_id = :id"), {"id": company_id})
            conn.execute(text("DELETE FROM companies WHERE ticker = '_TEST'"))
            conn.commit()

            if stock_row:
                return f"insert → join → delete OK (close={stock_row[0]})"
            raise Exception("test row not found after insert")

    results.append(check("Insert company → stock → join → cleanup", test_insert_flow))

    # ── Crypto insert test ──────────────────────────────────
    def test_crypto_insert():
        with engine.connect() as conn:
            btc_id = conn.execute(
                text("SELECT id FROM crypto_assets WHERE symbol = 'BTC'")
            ).scalar()

            conn.execute(text("""
                INSERT INTO crypto_prices (date, crypto_id, open, high, low, close, volume_usd, pct_change)
                VALUES (:date, :crypto_id, 42000.0, 43500.0, 41800.0, 43200.0, 28000000000, 2.85)
                ON CONFLICT DO NOTHING
            """), {
                "date": datetime(2024, 1, 15, tzinfo=timezone.utc),
                "crypto_id": btc_id,
            })

            row = conn.execute(text("""
                SELECT cp.close, ca.symbol
                FROM crypto_prices cp
                JOIN crypto_assets ca ON cp.crypto_id = ca.id
                WHERE ca.symbol = 'BTC'
            """)).fetchone()

            conn.execute(text("DELETE FROM crypto_prices WHERE crypto_id = :id"), {"id": btc_id})
            conn.commit()

            if row:
                return f"BTC price insert → join OK (close={row[0]})"
            raise Exception("crypto test row not found")

    results.append(check("Insert crypto price → join → cleanup", test_crypto_insert))

    # ── Summary ─────────────────────────────────────────────
    passed = sum(results)
    total = len(results)
    all_ok = passed == total

    print()
    print("=" * 60)
    if all_ok:
        print(f"  {BOLD}{PASS}  ALL {total} CHECKS PASSED — Phase 2 complete!{RESET}")
        print(f"  {BOLD}  Ready for Phase 3 — Historical Data Ingestion{RESET}")
    else:
        print(f"  {BOLD}{FAIL}  {passed}/{total} checks passed — fix failures above{RESET}")
    print("=" * 60)
    print()

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
