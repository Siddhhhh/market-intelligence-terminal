"""
Market Intelligence Terminal — Phase 8 Validation

Tests the enhanced top movers engine:
    1. Daily gainers/losers work
    2. Weekly period returns calculated correctly
    3. Monthly period returns calculated correctly
    4. Crypto movers work for all periods
    5. Summary endpoint returns both gainers and losers
    6. Historical dates work
    7. Sector info included in response

Run:
    Terminal 1: uvicorn backend.api.main:app --reload --port 8000
    Terminal 2: python scripts/validate_phase8.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx

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
    print(f"  {BOLD}PHASE 8 — TOP MOVERS ENGINE VALIDATION{RESET}")
    print("=" * 62)

    try:
        httpx.get(f"{BASE}/", timeout=5.0)
    except httpx.ConnectError:
        print(f"\n  {FAIL}  Cannot connect to {BASE}")
        sys.exit(1)

    results = []

    # ── Daily Stock Movers ──────────────────────────────────
    header("DAILY STOCK MOVERS")

    def check_daily_gainers():
        r = httpx.get(f"{BASE}/api/movers/gainers?period=daily&limit=5", timeout=10.0)
        assert r.status_code == 200
        data = r.json()
        assert len(data) > 0
        assert all(d["period"] == "daily" for d in data)
        top = data[0]
        return f"top: {top['ticker']} +{top['pct_change']:.2f}%, {len(data)} results"

    def check_daily_losers():
        r = httpx.get(f"{BASE}/api/movers/losers?period=daily&limit=5", timeout=10.0)
        assert r.status_code == 200
        data = r.json()
        assert len(data) > 0
        assert data[0]["pct_change"] < 0, "Top loser should be negative"
        top = data[0]
        return f"top: {top['ticker']} {top['pct_change']:.2f}%"

    def check_daily_has_sector():
        r = httpx.get(f"{BASE}/api/movers/gainers?period=daily&limit=5", timeout=10.0)
        data = r.json()
        has_sector = any(d.get("sector") for d in data)
        assert has_sector, "No sector info in response"
        return f"sector included: {data[0].get('sector')}"

    results.append(check("Daily gainers", check_daily_gainers))
    results.append(check("Daily losers", check_daily_losers))
    results.append(check("Sector info included", check_daily_has_sector))

    # ── Weekly Stock Movers ─────────────────────────────────
    header("WEEKLY STOCK MOVERS")

    def check_weekly_gainers():
        r = httpx.get(f"{BASE}/api/movers/gainers?period=weekly&limit=5", timeout=10.0)
        assert r.status_code == 200
        data = r.json()
        assert len(data) > 0
        assert all(d["period"] == "weekly" for d in data)
        top = data[0]
        return f"top: {top['ticker']} +{top['pct_change']:.2f}% over 5 days"

    def check_weekly_losers():
        r = httpx.get(f"{BASE}/api/movers/losers?period=weekly&limit=5", timeout=10.0)
        assert r.status_code == 200
        data = r.json()
        assert len(data) > 0
        top = data[0]
        return f"top: {top['ticker']} {top['pct_change']:.2f}% over 5 days"

    results.append(check("Weekly gainers", check_weekly_gainers))
    results.append(check("Weekly losers", check_weekly_losers))

    # ── Monthly Stock Movers ────────────────────────────────
    header("MONTHLY STOCK MOVERS")

    def check_monthly_gainers():
        r = httpx.get(f"{BASE}/api/movers/gainers?period=monthly&limit=5", timeout=10.0)
        assert r.status_code == 200
        data = r.json()
        assert len(data) > 0
        assert all(d["period"] == "monthly" for d in data)
        top = data[0]
        return f"top: {top['ticker']} +{top['pct_change']:.2f}% over 21 days"

    def check_monthly_losers():
        r = httpx.get(f"{BASE}/api/movers/losers?period=monthly&limit=5", timeout=10.0)
        assert r.status_code == 200
        data = r.json()
        assert len(data) > 0
        top = data[0]
        return f"top: {top['ticker']} {top['pct_change']:.2f}% over 21 days"

    results.append(check("Monthly gainers", check_monthly_gainers))
    results.append(check("Monthly losers", check_monthly_losers))

    # ── Crypto Movers ───────────────────────────────────────
    header("CRYPTO MOVERS")

    def check_crypto_daily():
        r = httpx.get(f"{BASE}/api/movers/gainers?period=daily&asset_type=crypto&limit=3", timeout=10.0)
        assert r.status_code == 200
        data = r.json()
        assert len(data) > 0
        return f"{len(data)} crypto daily movers"

    def check_crypto_weekly():
        r = httpx.get(f"{BASE}/api/movers/gainers?period=weekly&asset_type=crypto&limit=3", timeout=10.0)
        assert r.status_code == 200
        data = r.json()
        assert len(data) > 0
        top = data[0]
        return f"top crypto weekly: {top['ticker']} +{top['pct_change']:.2f}%"

    def check_crypto_monthly():
        r = httpx.get(f"{BASE}/api/movers/losers?period=monthly&asset_type=crypto&limit=3", timeout=10.0)
        assert r.status_code == 200
        data = r.json()
        assert len(data) > 0
        return f"{len(data)} crypto monthly losers"

    results.append(check("Crypto daily movers", check_crypto_daily))
    results.append(check("Crypto weekly movers", check_crypto_weekly))
    results.append(check("Crypto monthly movers", check_crypto_monthly))

    # ── Summary Endpoint ────────────────────────────────────
    header("SUMMARY ENDPOINT")

    def check_summary():
        r = httpx.get(f"{BASE}/api/movers/summary?period=daily&limit=5", timeout=10.0)
        assert r.status_code == 200
        data = r.json()
        assert "gainers" in data
        assert "losers" in data
        assert len(data["gainers"]) > 0
        assert len(data["losers"]) > 0
        return f"period={data['period']}, {len(data['gainers'])} gainers, {len(data['losers'])} losers"

    def check_summary_weekly():
        r = httpx.get(f"{BASE}/api/movers/summary?period=weekly&limit=5", timeout=10.0)
        assert r.status_code == 200
        data = r.json()
        assert data["period"] == "weekly"
        return f"weekly summary: {len(data['gainers'])} gainers, {len(data['losers'])} losers"

    results.append(check("Summary endpoint (daily)", check_summary))
    results.append(check("Summary endpoint (weekly)", check_summary_weekly))

    # ── Historical ──────────────────────────────────────────
    header("HISTORICAL MOVERS")

    def check_historical():
        r = httpx.get(f"{BASE}/api/movers/gainers?period=daily&date=2020-03-24&limit=5", timeout=10.0)
        assert r.status_code == 200
        data = r.json()
        if len(data) > 0:
            top = data[0]
            return f"2020-03-24 top gainer: {top['ticker']} +{top['pct_change']:.2f}%"
        return "no data for 2020-03-24"

    results.append(check("Historical date (COVID rebound)", check_historical))

    # ── Ranking Correctness ─────────────────────────────────
    header("RANKING CORRECTNESS")

    def check_gainers_sorted():
        r = httpx.get(f"{BASE}/api/movers/gainers?period=daily&limit=10", timeout=10.0)
        data = r.json()
        pcts = [d["pct_change"] for d in data]
        for i in range(len(pcts) - 1):
            assert pcts[i] >= pcts[i + 1], f"Not sorted: {pcts[i]} < {pcts[i+1]}"
        return f"correctly sorted descending ({pcts[0]:.2f}% → {pcts[-1]:.2f}%)"

    def check_losers_sorted():
        r = httpx.get(f"{BASE}/api/movers/losers?period=daily&limit=10", timeout=10.0)
        data = r.json()
        pcts = [d["pct_change"] for d in data]
        for i in range(len(pcts) - 1):
            assert pcts[i] <= pcts[i + 1], f"Not sorted: {pcts[i]} > {pcts[i+1]}"
        return f"correctly sorted ascending ({pcts[0]:.2f}% → {pcts[-1]:.2f}%)"

    results.append(check("Gainers sorted correctly", check_gainers_sorted))
    results.append(check("Losers sorted correctly", check_losers_sorted))

    # ── Summary ─────────────────────────────────────────────
    passed = sum(results)
    total = len(results)
    all_ok = passed == total

    print()
    print("=" * 62)
    if all_ok:
        print(f"  {BOLD}{PASS}  ALL {total} CHECKS PASSED — Phase 8 complete!{RESET}")
        print(f"  {BOLD}  Ready for Phase 9 — Daily Automation{RESET}")
    else:
        print(f"  {BOLD}{FAIL}  {passed}/{total} checks passed — fix failures above{RESET}")
    print("=" * 62)
    print()

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
