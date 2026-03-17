"""
Market Intelligence Terminal — Phase 8.5 Validation

Tests the comparison engine and universal date range support:
    1. Stock comparison across two periods
    2. Sector comparison across two periods
    3. Crypto comparison across two periods
    4. Diff metrics calculated correctly
    5. Historical comparisons (2008 vs 2023)
    6. Edge cases handled

Run:
    Terminal 1: uvicorn backend.api.main:app --reload --port 8000
    Terminal 2: python scripts/validate_phase8_5.py
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
    print(f"  {BOLD}PHASE 8.5 — COMPARISON ENGINE VALIDATION{RESET}")
    print("=" * 62)

    try:
        httpx.get(f"{BASE}/", timeout=5.0)
    except httpx.ConnectError:
        print(f"\n  {FAIL}  Cannot connect to {BASE}")
        sys.exit(1)

    results = []

    # ── Stock Comparison ────────────────────────────────────
    header("STOCK COMPARISON")

    def check_aapl_2008_vs_2023():
        r = httpx.get(f"{BASE}/api/compare/stock", params={
            "ticker": "AAPL",
            "p1_start": "2008-01-01", "p1_end": "2008-12-31",
            "p2_start": "2023-01-01", "p2_end": "2023-12-31",
        }, timeout=10.0)
        assert r.status_code == 200
        d = r.json()
        assert d["ticker"] == "AAPL"
        p1_ret = d["primary"]["total_return"]
        p2_ret = d["comparison"]["total_return"]
        diff = d["diff"]["return_diff"]
        return f"2008: {p1_ret}%, 2023: {p2_ret}%, diff: {diff}%"

    def check_nvda_comparison():
        r = httpx.get(f"{BASE}/api/compare/stock", params={
            "ticker": "NVDA",
            "p1_start": "2022-01-01", "p1_end": "2022-12-31",
            "p2_start": "2023-01-01", "p2_end": "2023-12-31",
        }, timeout=10.0)
        assert r.status_code == 200
        d = r.json()
        assert "primary" in d and "comparison" in d
        p1 = d["primary"]
        p2 = d["comparison"]
        assert p1["trading_days"] > 0
        assert p2["trading_days"] > 0
        return f"2022: {p1['total_return']}%, 2023: {p2['total_return']}%, direction: {d['diff']['direction']}"

    def check_comparison_has_metrics():
        r = httpx.get(f"{BASE}/api/compare/stock", params={
            "ticker": "MSFT",
            "p1_start": "2024-01-01", "p1_end": "2024-06-30",
            "p2_start": "2024-07-01", "p2_end": "2024-12-31",
        }, timeout=10.0)
        assert r.status_code == 200
        d = r.json()
        p = d["primary"]
        assert p.get("volatility") is not None, "Missing volatility"
        assert p.get("best_day") is not None, "Missing best_day"
        assert p.get("worst_day") is not None, "Missing worst_day"
        return f"volatility={p['volatility']}, best={p['best_day']['pct']}%, worst={p['worst_day']['pct']}%"

    def check_invalid_ticker():
        r = httpx.get(f"{BASE}/api/compare/stock", params={
            "ticker": "ZZZZZZ",
            "p1_start": "2023-01-01", "p1_end": "2023-12-31",
            "p2_start": "2024-01-01", "p2_end": "2024-12-31",
        }, timeout=10.0)
        assert r.status_code == 404
        return "404 for invalid ticker"

    results.append(check("AAPL 2008 vs 2023", check_aapl_2008_vs_2023))
    results.append(check("NVDA 2022 vs 2023", check_nvda_comparison))
    results.append(check("Metrics: volatility, best/worst day", check_comparison_has_metrics))
    results.append(check("Invalid ticker returns 404", check_invalid_ticker))

    # ── Sector Comparison ───────────────────────────────────
    header("SECTOR COMPARISON")

    def check_sectors_pre_post_covid():
        r = httpx.get(f"{BASE}/api/compare/sector", params={
            "p1_start": "2019-01-01", "p1_end": "2019-12-31",
            "p2_start": "2021-01-01", "p2_end": "2021-12-31",
        }, timeout=15.0)
        assert r.status_code == 200
        d = r.json()
        assert "primary_sectors" in d
        assert "comparison_sectors" in d
        assert "diffs" in d
        p1_count = len(d["primary_sectors"])
        p2_count = len(d["comparison_sectors"])
        return f"primary: {p1_count} sectors, comparison: {p2_count} sectors"

    def check_single_sector_compare():
        r = httpx.get(f"{BASE}/api/compare/sector", params={
            "p1_start": "2020-01-01", "p1_end": "2020-12-31",
            "p2_start": "2024-01-01", "p2_end": "2024-12-31",
            "sector": "technology",
        }, timeout=15.0)
        assert r.status_code == 200
        d = r.json()
        assert "technology" in d["primary_sectors"]
        tech_diff = d["diffs"].get("technology", {})
        return f"tech 2020 vs 2024, direction: {tech_diff.get('direction', 'N/A')}"

    def check_sector_diffs():
        r = httpx.get(f"{BASE}/api/compare/sector", params={
            "p1_start": "2023-01-01", "p1_end": "2023-06-30",
            "p2_start": "2023-07-01", "p2_end": "2023-12-31",
        }, timeout=15.0)
        assert r.status_code == 200
        d = r.json()
        diffs = d["diffs"]
        assert len(diffs) > 0
        has_direction = all("direction" in v for v in diffs.values())
        assert has_direction
        return f"{len(diffs)} sectors compared with direction indicators"

    results.append(check("Sectors pre vs post COVID", check_sectors_pre_post_covid))
    results.append(check("Single sector (technology)", check_single_sector_compare))
    results.append(check("Sector diffs have direction", check_sector_diffs))

    # ── Crypto Comparison ───────────────────────────────────
    header("CRYPTO COMPARISON")

    def check_btc_comparison():
        r = httpx.get(f"{BASE}/api/compare/crypto", params={
            "symbol": "BTC",
            "p1_start": "2021-01-01", "p1_end": "2021-12-31",
            "p2_start": "2024-01-01", "p2_end": "2024-12-31",
        }, timeout=10.0)
        assert r.status_code == 200
        d = r.json()
        assert d["symbol"] == "BTC"
        p1_ret = d["primary"]["total_return"]
        p2_ret = d["comparison"]["total_return"]
        return f"BTC 2021: {p1_ret}%, 2024: {p2_ret}%"

    def check_eth_comparison():
        r = httpx.get(f"{BASE}/api/compare/crypto", params={
            "symbol": "ETH",
            "p1_start": "2022-01-01", "p1_end": "2022-12-31",
            "p2_start": "2023-01-01", "p2_end": "2023-12-31",
        }, timeout=10.0)
        assert r.status_code == 200
        d = r.json()
        assert "diff" in d
        return f"ETH comparison, direction: {d['diff']['direction']}"

    results.append(check("BTC 2021 vs 2024", check_btc_comparison))
    results.append(check("ETH 2022 vs 2023", check_eth_comparison))

    # ── Date Range on Existing Endpoints ────────────────────
    header("UNIVERSAL DATE RANGE (existing endpoints)")

    def check_stocks_date_range():
        r = httpx.get(f"{BASE}/api/stocks/AAPL", params={
            "start_date": "2020-01-01", "end_date": "2020-06-30",
        }, timeout=10.0)
        assert r.status_code == 200
        d = r.json()
        assert d["total_records"] > 0
        return f"AAPL H1 2020: {d['total_records']} records"

    def check_heatmap_date():
        r = httpx.get(f"{BASE}/api/heatmap?date=2023-06-15", timeout=10.0)
        assert r.status_code == 200
        d = r.json()
        assert len(d) > 0
        return f"heatmap for 2023-06-15: {len(d)} sectors"

    def check_movers_date():
        r = httpx.get(f"{BASE}/api/movers/gainers?date=2024-03-15&period=daily&limit=3", timeout=10.0)
        assert r.status_code == 200
        d = r.json()
        assert len(d) > 0
        return f"movers for 2024-03-15: top={d[0]['ticker']}"

    results.append(check("Stock date range filtering", check_stocks_date_range))
    results.append(check("Heatmap custom date", check_heatmap_date))
    results.append(check("Movers custom date", check_movers_date))

    # ── Summary ─────────────────────────────────────────────
    passed = sum(results)
    total = len(results)
    all_ok = passed == total

    print()
    print("=" * 62)
    if all_ok:
        print(f"  {BOLD}{PASS}  ALL {total} CHECKS PASSED — Phase 8.5 complete!{RESET}")
        print(f"  {BOLD}  Ready for Phase 9 — Daily Automation{RESET}")
    else:
        print(f"  {BOLD}{FAIL}  {passed}/{total} checks passed — fix failures above{RESET}")
    print("=" * 62)
    print()

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
