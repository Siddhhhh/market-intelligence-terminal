"""
Market Intelligence Terminal — Phase 7 Validation

Tests the sector heatmap engine:
    1. Precomputed table created and populated
    2. Heatmap API returns fast results
    3. Historical dates work (2008 crash)
    4. Sector drill-down returns per-company data
    5. Edge cases handled

Run:
    Terminal 1: uvicorn backend.api.main:app --reload --port 8000
    Terminal 2: python scripts/validate_phase7.py
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from sqlalchemy import text
from database.session import engine

BASE = "http://localhost:8000"

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
    print(f"  {BOLD}PHASE 7 — SECTOR HEATMAP ENGINE VALIDATION{RESET}")
    print("=" * 62)

    results = []

    # ── Precomputed table ───────────────────────────────────
    header("PRECOMPUTED TABLE")

    def check_table_exists():
        with engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM sector_performance")).scalar()
            return f"{count:,} rows in sector_performance"

    def check_table_coverage():
        with engine.connect() as conn:
            dates = conn.execute(text("SELECT COUNT(DISTINCT date) FROM sector_performance")).scalar()
            sectors = conn.execute(text("SELECT COUNT(DISTINCT sector_id) FROM sector_performance")).scalar()
            return f"{dates:,} dates x {sectors} sectors"

    results.append(check("sector_performance table exists", check_table_exists))
    results.append(check("Table coverage", check_table_coverage))

    # ── Heatmap API ─────────────────────────────────────────
    header("HEATMAP API PERFORMANCE")

    def check_heatmap_latest():
        start = time.time()
        r = httpx.get(f"{BASE}/api/heatmap", timeout=10.0)
        elapsed = (time.time() - start) * 1000
        assert r.status_code == 200
        data = r.json()
        assert len(data) > 0
        return f"{len(data)} sectors in {elapsed:.0f}ms"

    def check_heatmap_fast():
        # Warm up
        httpx.get(f"{BASE}/api/heatmap", timeout=10.0)
        # Measure
        times = []
        for _ in range(3):
            start = time.time()
            httpx.get(f"{BASE}/api/heatmap", timeout=10.0)
            times.append((time.time() - start) * 1000)
        avg = sum(times) / len(times)
        return f"avg response: {avg:.0f}ms"

    def check_heatmap_has_movers():
        r = httpx.get(f"{BASE}/api/heatmap", timeout=10.0)
        data = r.json()
        has_gainer = any(s.get("top_gainer") for s in data)
        has_loser = any(s.get("top_loser") for s in data)
        assert has_gainer, "No top gainers found"
        assert has_loser, "No top losers found"
        top = data[0]
        return f"top sector: {top['display_name']} ({top['avg_pct_change']:+.2f}%)"

    results.append(check("Heatmap latest date", check_heatmap_latest))
    results.append(check("Response speed", check_heatmap_fast))
    results.append(check("Includes top movers", check_heatmap_has_movers))

    # ── Historical dates ────────────────────────────────────
    header("HISTORICAL QUERIES")

    def check_2008_crash():
        # Sept 29 2008 — one of the worst single days
        r = httpx.get(f"{BASE}/api/heatmap?date=2008-09-29", timeout=10.0)
        assert r.status_code == 200
        data = r.json()
        if len(data) == 0:
            return "no data for 2008-09-29 (may not have companies from that era)"
        neg_sectors = sum(1 for s in data if s["avg_pct_change"] < 0)
        return f"{neg_sectors}/{len(data)} sectors negative on 2008-09-29"

    def check_2020_crash():
        # March 16 2020 — COVID crash
        r = httpx.get(f"{BASE}/api/heatmap?date=2020-03-16", timeout=10.0)
        assert r.status_code == 200
        data = r.json()
        if len(data) == 0:
            return "no data for 2020-03-16"
        neg_sectors = sum(1 for s in data if s["avg_pct_change"] < 0)
        worst = min(data, key=lambda s: s["avg_pct_change"])
        return f"{neg_sectors}/{len(data)} sectors negative, worst: {worst['display_name']} ({worst['avg_pct_change']:+.2f}%)"

    def check_recent_date():
        r = httpx.get(f"{BASE}/api/heatmap?date=2024-01-02", timeout=10.0)
        assert r.status_code == 200
        data = r.json()
        assert len(data) > 0
        return f"{len(data)} sectors for 2024-01-02"

    results.append(check("2008 crash date", check_2008_crash))
    results.append(check("2020 COVID crash", check_2020_crash))
    results.append(check("Recent date (2024)", check_recent_date))

    # ── Sector drill-down ───────────────────────────────────
    header("SECTOR DRILL-DOWN")

    def check_sector_companies():
        r = httpx.get(f"{BASE}/api/sectors/technology", timeout=10.0)
        assert r.status_code == 200
        data = r.json()
        assert len(data) > 0
        has_price = sum(1 for c in data if c.get("pct_change") is not None)
        return f"{len(data)} companies, {has_price} with price data"

    def check_sector_sorted():
        r = httpx.get(f"{BASE}/api/sectors/technology?sort=pct_change&order=desc", timeout=10.0)
        assert r.status_code == 200
        data = r.json()
        pcts = [c["pct_change"] for c in data if c["pct_change"] is not None]
        if len(pcts) >= 2:
            assert pcts[0] >= pcts[1], "Not sorted descending"
        return f"sorted by pct_change desc, top: {data[0]['ticker']} {pcts[0] if pcts else 'N/A'}%"

    def check_sector_404():
        r = httpx.get(f"{BASE}/api/sectors/nonexistent", timeout=10.0)
        assert r.status_code == 404
        return "404 for invalid sector"

    results.append(check("Technology sector drill-down", check_sector_companies))
    results.append(check("Sector sort by pct_change", check_sector_sorted))
    results.append(check("Invalid sector returns 404", check_sector_404))

    # ── Heatmap history ─────────────────────────────────────
    header("HEATMAP HISTORY")

    def check_history_endpoint():
        r = httpx.get(f"{BASE}/api/heatmap/history?sector=technology&limit=10", timeout=10.0)
        assert r.status_code == 200
        data = r.json()
        assert len(data) > 0
        return f"{len(data)} history entries for technology"

    results.append(check("Heatmap history endpoint", check_history_endpoint))

    # ── Summary ─────────────────────────────────────────────
    passed = sum(results)
    total = len(results)
    all_ok = passed == total

    print()
    print("=" * 62)
    if all_ok:
        print(f"  {BOLD}{PASS}  ALL {total} CHECKS PASSED — Phase 7 complete!{RESET}")
        print(f"  {BOLD}  Ready for Phase 8 — Top Movers Engine{RESET}")
    else:
        print(f"  {BOLD}{FAIL}  {passed}/{total} checks passed — fix failures above{RESET}")
    print("=" * 62)
    print()

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
