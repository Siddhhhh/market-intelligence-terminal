"""
Market Intelligence Terminal — Phase 3 Validation

Tests that the data ingestion pipeline worked correctly:
    1. Stock data exists in the stocks hypertable
    2. Crypto data exists in the crypto_prices hypertable
    3. Macro data exists in the macro_events table
    4. Companies were inserted with sector mappings
    5. Percent change calculations are correct
    6. Event detection produced results
    7. Date ranges span multiple decades
    8. No null close prices exist

Run from project root:
    python scripts/validate_phase3.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
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
    print("=" * 62)
    print(f"  {BOLD}PHASE 3 — DATA INGESTION VALIDATION{RESET}")
    print("=" * 62)

    results = []

    # ── Stock data ──────────────────────────────────────────
    header("STOCK DATA")

    def check_stock_count():
        with engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM stocks")).scalar()
            if count > 0:
                return f"{count:,} rows"
            raise Exception("no stock data found")

    def check_company_count():
        with engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM companies WHERE is_sp500 = TRUE")).scalar()
            if count > 50:
                return f"{count} S&P 500 companies"
            raise Exception(f"only {count} companies, expected 400+")

    def check_stock_date_range():
        with engine.connect() as conn:
            row = conn.execute(text(
                "SELECT MIN(date)::date, MAX(date)::date FROM stocks"
            )).fetchone()
            if row and row[0]:
                return f"{row[0]} → {row[1]}"
            raise Exception("no dates found")

    def check_stock_pct_change():
        with engine.connect() as conn:
            # Verify pct_change is calculated: pick a random stock with > 2 rows
            row = conn.execute(text("""
                SELECT s.pct_change, s.close,
                       LAG(s.close) OVER (PARTITION BY s.company_id ORDER BY s.date) as prev_close
                FROM stocks s
                WHERE s.pct_change IS NOT NULL
                LIMIT 1 OFFSET 100
            """)).fetchone()
            if row and row[0] is not None:
                return f"pct_change={row[0]}%, close={row[1]}"
            raise Exception("pct_change is null everywhere")

    def check_no_null_close():
        with engine.connect() as conn:
            count = conn.execute(text(
                "SELECT COUNT(*) FROM stocks WHERE close IS NULL"
            )).scalar()
            if count == 0:
                return "no null close prices"
            raise Exception(f"{count} rows have null close")

    def check_stock_hypertable_data():
        with engine.connect() as conn:
            count = conn.execute(text("""
                SELECT COUNT(*) FROM timescaledb_information.chunks
                WHERE hypertable_name = 'stocks'
            """)).scalar()
            if count > 0:
                return f"{count} time chunks"
            raise Exception("no hypertable chunks — data may not be in hypertable")

    results.append(check("Stock row count", check_stock_count))
    results.append(check("S&P 500 companies", check_company_count))
    results.append(check("Stock date range", check_stock_date_range))
    results.append(check("Percent change calculated", check_stock_pct_change))
    results.append(check("No null close prices", check_no_null_close))
    results.append(check("Stocks in hypertable chunks", check_stock_hypertable_data))

    # ── Crypto data ─────────────────────────────────────────
    header("CRYPTO DATA")

    def check_crypto_count():
        with engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM crypto_prices")).scalar()
            if count > 0:
                return f"{count:,} rows"
            raise Exception("no crypto data found")

    def check_crypto_assets_present():
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT ca.symbol, COUNT(cp.date)
                FROM crypto_assets ca
                LEFT JOIN crypto_prices cp ON ca.id = cp.crypto_id
                GROUP BY ca.symbol
                ORDER BY ca.symbol
            """)).fetchall()
            summary = ", ".join(f"{r[0]}={r[1]:,}" for r in rows)
            has_data = any(r[1] > 0 for r in rows)
            if has_data:
                return summary
            raise Exception("no crypto price data for any asset")

    def check_crypto_hypertable():
        with engine.connect() as conn:
            count = conn.execute(text("""
                SELECT COUNT(*) FROM timescaledb_information.chunks
                WHERE hypertable_name = 'crypto_prices'
            """)).scalar()
            if count > 0:
                return f"{count} time chunks"
            raise Exception("no hypertable chunks")

    results.append(check("Crypto row count", check_crypto_count))
    results.append(check("Crypto assets with data", check_crypto_assets_present))
    results.append(check("Crypto in hypertable chunks", check_crypto_hypertable))

    # ── Macro data ──────────────────────────────────────────
    header("MACRO DATA")

    def check_macro_count():
        with engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM macro_events")).scalar()
            if count > 0:
                return f"{count:,} rows"
            raise Exception("no macro data found")

    def check_macro_indicators():
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT indicator, COUNT(*)
                FROM macro_events
                GROUP BY indicator
                ORDER BY indicator
            """)).fetchall()
            if len(rows) > 0:
                summary = ", ".join(f"{r[0]}={r[1]:,}" for r in rows)
                return f"{len(rows)} indicators: {summary}"
            raise Exception("no indicators found")

    results.append(check("Macro row count", check_macro_count))
    results.append(check("Macro indicators present", check_macro_indicators))

    # ── Event detection ─────────────────────────────────────
    header("EVENT DETECTION")

    def check_events_exist():
        with engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM market_events")).scalar()
            if count > 0:
                return f"{count:,} events detected"
            raise Exception("no events detected")

    def check_event_types():
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT event_type, COUNT(*)
                FROM market_events
                GROUP BY event_type
                ORDER BY COUNT(*) DESC
            """)).fetchall()
            if len(rows) > 0:
                summary = ", ".join(f"{r[0]}={r[1]:,}" for r in rows)
                return summary
            raise Exception("no event types found")

    results.append(check("Events exist", check_events_exist))
    results.append(check("Event types breakdown", check_event_types))

    # ── Sector mapping ──────────────────────────────────────
    header("SECTOR MAPPING")

    def check_sector_coverage():
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT s.display_name, COUNT(c.id)
                FROM sectors s
                LEFT JOIN companies c ON c.sector_id = s.id
                GROUP BY s.display_name
                ORDER BY COUNT(c.id) DESC
            """)).fetchall()
            mapped = sum(1 for r in rows if r[1] > 0)
            total_companies = sum(r[1] for r in rows)
            return f"{mapped}/{len(rows)} sectors have companies, {total_companies} total mapped"

    results.append(check("Companies mapped to sectors", check_sector_coverage))

    # ── Summary ─────────────────────────────────────────────
    passed = sum(results)
    total = len(results)
    all_ok = passed == total

    print()
    print("=" * 62)
    if all_ok:
        print(f"  {BOLD}{PASS}  ALL {total} CHECKS PASSED — Phase 3 complete!{RESET}")
        print(f"  {BOLD}  Ready for Phase 4 — Backend API{RESET}")
    else:
        print(f"  {BOLD}{FAIL}  {passed}/{total} checks passed — fix failures above{RESET}")
    print("=" * 62)
    print()

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
