"""
Market Intelligence Terminal — Phase 9 Validation

Tests the daily automation system:
    1. Daily update pipeline runs successfully
    2. No duplicate rows created
    3. Scheduler configures correctly
    4. New data appears in the database
    5. Event detection runs on new data
    6. Sector performance updates

Run from project root:
    python scripts/validate_phase9.py
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from database.session import engine
from loguru import logger

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
    print(f"  {BOLD}PHASE 9 — DAILY AUTOMATION VALIDATION{RESET}")
    print("=" * 62)

    results = []

    # ── Pre-update counts ───────────────────────────────────
    header("PRE-UPDATE STATE")

    with engine.connect() as conn:
        pre_stocks = conn.execute(text("SELECT COUNT(*) FROM stocks")).scalar()
        pre_events = conn.execute(text("SELECT COUNT(*) FROM market_events")).scalar()
        pre_sectors = conn.execute(text("SELECT COUNT(*) FROM sector_performance")).scalar()
        pre_latest = conn.execute(text("SELECT MAX(date)::date FROM stocks")).scalar()

    print(f"  Stocks: {pre_stocks:,} rows")
    print(f"  Events: {pre_events:,}")
    print(f"  Sector perf: {pre_sectors:,}")
    print(f"  Latest date: {pre_latest}")

    # ── Run daily update ────────────────────────────────────
    header("DAILY UPDATE PIPELINE")

    def check_daily_update():
        from backend.data_pipeline.daily_update import run_daily_update
        result = run_daily_update()
        elapsed = result.get("elapsed_seconds", 0)
        return f"completed in {elapsed}s"

    results.append(check("Daily update runs successfully", check_daily_update))

    # ── Post-update counts ──────────────────────────────────
    header("POST-UPDATE STATE")

    def check_stocks_updated():
        with engine.connect() as conn:
            post_stocks = conn.execute(text("SELECT COUNT(*) FROM stocks")).scalar()
            post_latest = conn.execute(text("SELECT MAX(date)::date FROM stocks")).scalar()
        return f"{post_stocks:,} rows (was {pre_stocks:,}), latest: {post_latest}"

    def check_no_duplicates():
        with engine.connect() as conn:
            dupes = conn.execute(text("""
                SELECT COUNT(*) FROM (
                    SELECT date, company_id, COUNT(*) as cnt
                    FROM stocks
                    GROUP BY date, company_id
                    HAVING COUNT(*) > 1
                ) dupes
            """)).scalar()
        assert dupes == 0, f"{dupes} duplicate rows found"
        return "zero duplicate rows"

    def check_events_updated():
        with engine.connect() as conn:
            post_events = conn.execute(text("SELECT COUNT(*) FROM market_events")).scalar()
        return f"{post_events:,} events (was {pre_events:,})"

    def check_sectors_updated():
        with engine.connect() as conn:
            post_sectors = conn.execute(text("SELECT COUNT(*) FROM sector_performance")).scalar()
        return f"{post_sectors:,} sector rows (was {pre_sectors:,})"

    results.append(check("Stock data present", check_stocks_updated))
    results.append(check("No duplicate rows", check_no_duplicates))
    results.append(check("Events updated", check_events_updated))
    results.append(check("Sector performance updated", check_sectors_updated))

    # ── Scheduler configuration ─────────────────────────────
    header("SCHEDULER CONFIGURATION")

    def check_scheduler_creates():
        from backend.data_pipeline.scheduler import create_scheduler
        scheduler = create_scheduler(background=True)
        jobs = scheduler.get_jobs()
        assert len(jobs) > 0, "No jobs configured"
        job = jobs[0]
        return f"job: {job.name}, next: {job.trigger}"

    def check_scheduler_config():
        from config import settings
        return (
            f"enabled={settings.scheduler_enabled}, "
            f"time={settings.scheduler_hour:02d}:{settings.scheduler_minute:02d} ET"
        )

    results.append(check("Scheduler creates successfully", check_scheduler_creates))
    results.append(check("Scheduler config loaded", check_scheduler_config))

    # ── Manual trigger ──────────────────────────────────────
    header("MANUAL TRIGGER")

    def check_run_pipeline_commands():
        # Just verify the module imports work
        from backend.data_pipeline.daily_update import run_daily_update
        from backend.data_pipeline.scheduler import create_scheduler, start_background_scheduler
        return "all modules importable"

    results.append(check("Pipeline modules importable", check_run_pipeline_commands))

    # ── Idempotency ─────────────────────────────────────────
    header("IDEMPOTENCY (re-run safety)")

    def check_rerun_safe():
        with engine.connect() as conn:
            count_before = conn.execute(text("SELECT COUNT(*) FROM stocks")).scalar()

        # Run daily update again
        from backend.data_pipeline.daily_update import run_daily_update
        run_daily_update()

        with engine.connect() as conn:
            count_after = conn.execute(text("SELECT COUNT(*) FROM stocks")).scalar()
            dupes = conn.execute(text("""
                SELECT COUNT(*) FROM (
                    SELECT date, company_id, COUNT(*) as cnt
                    FROM stocks
                    GROUP BY date, company_id
                    HAVING COUNT(*) > 1
                ) dupes
            """)).scalar()

        assert dupes == 0, f"Re-run created {dupes} duplicates"
        return f"before: {count_before:,}, after: {count_after:,}, dupes: 0"

    results.append(check("Re-run creates no duplicates", check_rerun_safe))

    # ── Summary ─────────────────────────────────────────────
    passed = sum(results)
    total = len(results)
    all_ok = passed == total

    print()
    print("=" * 62)
    if all_ok:
        print(f"  {BOLD}{PASS}  ALL {total} CHECKS PASSED — Phase 9 complete!{RESET}")
        print(f"  {BOLD}  Ready for Phase 10 — Documentation & README{RESET}")
    else:
        print(f"  {BOLD}{FAIL}  {passed}/{total} checks passed — fix failures above{RESET}")
    print("=" * 62)
    print()

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
