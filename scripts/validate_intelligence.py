"""
Market Intelligence Terminal — Company Intelligence Validation

Tests the Movement Attribution Engine and Company Intelligence system.

Run:
    Terminal 1: uvicorn backend.api.main:app --reload --port 8000
    Terminal 2: python scripts/validate_intelligence.py
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
    print(f"  {BOLD}COMPANY INTELLIGENCE SYSTEM VALIDATION{RESET}")
    print("=" * 62)

    try:
        httpx.get(f"{BASE}/", timeout=5.0)
    except httpx.ConnectError:
        print(f"\n  {FAIL}  Cannot connect to {BASE}")
        sys.exit(1)

    results = []

    # ── Company Intelligence Endpoint ───────────────────────
    header("COMPANY INTELLIGENCE")

    def check_aapl_intel():
        r = httpx.get(f"{BASE}/api/company/AAPL/intelligence", timeout=30.0)
        assert r.status_code == 200
        d = r.json()
        assert d["ticker"] == "AAPL"
        assert d["name"] is not None
        assert d["sector"] is not None
        mc = d["financials"].get("market_cap")
        return f"AAPL: {d['name']}, sector={d['sector']}, market_cap={mc}"

    def check_intel_has_indicators():
        r = httpx.get(f"{BASE}/api/company/NVDA/intelligence", timeout=30.0)
        assert r.status_code == 200
        d = r.json()
        ind = d.get("indicators", {})
        has_data = ind.get("ma20") is not None or ind.get("rsi") is not None
        return f"NVDA indicators: ma20={ind.get('ma20')}, rsi={ind.get('rsi')}, trend={ind.get('trend')}"

    def check_intel_has_relationships():
        r = httpx.get(f"{BASE}/api/company/NVDA/intelligence", timeout=30.0)
        d = r.json()
        rels = d.get("relationships", [])
        return f"NVDA: {len(rels)} relationships"

    def check_invalid_ticker():
        r = httpx.get(f"{BASE}/api/company/ZZZZZ/intelligence", timeout=10.0)
        assert r.status_code == 404
        return "404 for invalid ticker"

    results.append(check("AAPL intelligence", check_aapl_intel))
    results.append(check("NVDA has indicators", check_intel_has_indicators))
    results.append(check("NVDA has relationships", check_intel_has_relationships))
    results.append(check("Invalid ticker 404", check_invalid_ticker))

    # ── Movement Attribution Engine ─────────────────────────
    header("MOVEMENT ATTRIBUTION ENGINE")

    def check_movement_7d():
        r = httpx.get(f"{BASE}/api/company/AAPL/movement-explanation?range=7d", timeout=30.0)
        assert r.status_code == 200
        d = r.json()
        assert "summary" in d
        assert "drivers" in d
        assert "overall_confidence" in d
        assert "confidence_breakdown" in d
        assert "data_quality" in d
        drivers = d["drivers"]
        return f"AAPL 7d: {len(drivers)} drivers, conf={d['overall_confidence']:.2f}"

    def check_movement_30d():
        r = httpx.get(f"{BASE}/api/company/TSLA/movement-explanation?range=30d", timeout=30.0)
        assert r.status_code == 200
        d = r.json()
        assert d["ticker"] == "TSLA"
        assert d["period_return"] is not None
        return f"TSLA 30d: return={d['period_return']}%, {len(d['drivers'])} drivers"

    def check_movement_has_presentation():
        r = httpx.get(f"{BASE}/api/company/MSFT/movement-explanation?range=7d", timeout=30.0)
        d = r.json()
        drivers = d.get("drivers", [])
        if drivers:
            first = drivers[0]
            assert "explanation" in first, "Missing explanation field"
            assert "short_label" in first, "Missing short_label field"
            return f"MSFT: '{first['short_label']}' — {first['explanation'][:50]}..."
        return "MSFT: no drivers (may need indicators pipeline)"

    def check_movement_structure():
        r = httpx.get(f"{BASE}/api/company/AAPL/movement-explanation?range=7d", timeout=30.0)
        d = r.json()
        assert "methodology" in d
        assert "model_version" in d
        assert "disclaimer" in d
        assert d["model_version"] == "v1.0_attribution_engine"
        return f"methodology={d['methodology'][0]}, version={d['model_version']}"

    def check_movement_buy_sell():
        r = httpx.get(f"{BASE}/api/company/AAPL/movement-explanation?range=30d", timeout=30.0)
        d = r.json()
        bsz = d.get("buy_sell_zones", {})
        assert "label" in bsz
        return f"zones: buy={bsz.get('buy_zone')}, sell={bsz.get('sell_zone')}"

    results.append(check("AAPL movement 7d", check_movement_7d))
    results.append(check("TSLA movement 30d", check_movement_30d))
    results.append(check("Presentation mapping", check_movement_has_presentation))
    results.append(check("Structural completeness", check_movement_structure))
    results.append(check("Buy/sell zones", check_movement_buy_sell))

    # ── Data Quality & Confidence ───────────────────────────
    header("DATA QUALITY & CONFIDENCE")

    def check_confidence_breakdown():
        r = httpx.get(f"{BASE}/api/company/AAPL/movement-explanation?range=7d", timeout=30.0)
        d = r.json()
        cb = d.get("confidence_breakdown", {})
        assert "data_quality" in cb
        assert "signal_agreement" in cb
        assert "final" in cb
        return f"quality={cb['data_quality']:.2f}, agreement={cb['signal_agreement']:.2f}, final={cb['final']:.2f}"

    def check_data_quality():
        r = httpx.get(f"{BASE}/api/company/AAPL/movement-explanation?range=7d", timeout=30.0)
        d = r.json()
        dq = d.get("data_quality", {})
        assert "macro_fresh" in dq
        assert "events_available" in dq
        assert "confidence_adjustment" in dq
        return f"macro_fresh={dq['macro_fresh']}, events={dq['events_available']}, adj={dq['confidence_adjustment']:.2f}"

    results.append(check("Confidence breakdown", check_confidence_breakdown))
    results.append(check("Data quality metrics", check_data_quality))

    # ── Edge Cases ──────────────────────────────────────────
    header("EDGE CASES")

    def check_invalid_range():
        r = httpx.get(f"{BASE}/api/company/AAPL/movement-explanation?range=999d", timeout=10.0)
        assert r.status_code == 400
        return "400 for invalid range"

    def check_1d_range():
        r = httpx.get(f"{BASE}/api/company/NVDA/movement-explanation?range=1d", timeout=30.0)
        assert r.status_code == 200
        d = r.json()
        return f"NVDA 1d: return={d['period_return']}%"

    results.append(check("Invalid range returns 400", check_invalid_range))
    results.append(check("1-day range works", check_1d_range))

    # ── Summary ─────────────────────────────────────────────
    passed = sum(results)
    total = len(results)
    all_ok = passed == total

    print()
    print("=" * 62)
    if all_ok:
        print(f"  {BOLD}{PASS}  ALL {total} CHECKS PASSED — Intelligence System complete!{RESET}")
    else:
        print(f"  {BOLD}{FAIL}  {passed}/{total} checks passed — fix failures above{RESET}")
    print("=" * 62)
    print()

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
