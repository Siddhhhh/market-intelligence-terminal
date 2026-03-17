"""
Market Intelligence Terminal — Phase 4 Validation

Tests all API endpoints by making HTTP requests to the running server.

IMPORTANT: Start the API server first in a separate terminal:
    uvicorn backend.api.main:app --reload --port 8000

Then run this script:
    python scripts/validate_phase4.py
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
    print(f"  {BOLD}PHASE 4 — API ENDPOINT VALIDATION{RESET}")
    print(f"  Server: {BASE}")
    print("=" * 62)

    # Check server is running
    try:
        httpx.get(f"{BASE}/", timeout=5.0)
    except httpx.ConnectError:
        print(f"\n  {FAIL}  Cannot connect to {BASE}")
        print(f"       Start the server first:")
        print(f"       uvicorn backend.api.main:app --reload --port 8000")
        sys.exit(1)

    results = []

    # ── Health ──────────────────────────────────────────────
    header("HEALTH")

    def check_root():
        r = httpx.get(f"{BASE}/")
        assert r.status_code == 200
        data = r.json()
        return f"status={data['status']}, version={data['version']}"

    def check_stats():
        r = httpx.get(f"{BASE}/api/stats")
        assert r.status_code == 200
        data = r.json()
        return f"companies={data['database']['companies']}, stocks={data['database']['stocks']:,}"

    results.append(check("GET /", check_root))
    results.append(check("GET /api/stats", check_stats))

    # ── Stocks ──────────────────────────────────────────────
    header("STOCKS")

    def check_list_companies():
        r = httpx.get(f"{BASE}/api/stocks", params={"limit": 5})
        assert r.status_code == 200
        data = r.json()
        assert len(data) > 0
        return f"{len(data)} companies returned"

    def check_search_companies():
        r = httpx.get(f"{BASE}/api/stocks", params={"search": "apple"})
        assert r.status_code == 200
        data = r.json()
        assert len(data) > 0
        return f"found {len(data)} match(es) for 'apple'"

    def check_aapl_history():
        r = httpx.get(f"{BASE}/api/stocks/AAPL", params={"limit": 10})
        assert r.status_code == 200
        data = r.json()
        assert data["ticker"] == "AAPL"
        assert data["total_records"] > 0
        return f"{data['total_records']} records, company={data['company_name']}"

    def check_aapl_date_range():
        r = httpx.get(f"{BASE}/api/stocks/AAPL", params={
            "start_date": "2024-01-01", "end_date": "2024-12-31"
        })
        assert r.status_code == 200
        data = r.json()
        return f"{data['total_records']} records in 2024"

    def check_invalid_ticker():
        r = httpx.get(f"{BASE}/api/stocks/ZZZZZZ")
        assert r.status_code == 404
        return "404 returned correctly"

    results.append(check("GET /api/stocks (list)", check_list_companies))
    results.append(check("GET /api/stocks?search=apple", check_search_companies))
    results.append(check("GET /api/stocks/AAPL", check_aapl_history))
    results.append(check("GET /api/stocks/AAPL (date range)", check_aapl_date_range))
    results.append(check("GET /api/stocks/ZZZZZZ (404)", check_invalid_ticker))

    # ── Crypto ──────────────────────────────────────────────
    header("CRYPTO")

    def check_crypto_list():
        r = httpx.get(f"{BASE}/api/crypto")
        assert r.status_code == 200
        data = r.json()
        symbols = [a["symbol"] for a in data]
        return f"{len(data)} assets: {', '.join(symbols)}"

    def check_btc_history():
        r = httpx.get(f"{BASE}/api/crypto/BTC", params={"limit": 10})
        assert r.status_code == 200
        data = r.json()
        assert data["symbol"] == "BTC"
        return f"{data['total_records']} records"

    results.append(check("GET /api/crypto", check_crypto_list))
    results.append(check("GET /api/crypto/BTC", check_btc_history))

    # ── Events ──────────────────────────────────────────────
    header("EVENTS")

    def check_events():
        r = httpx.get(f"{BASE}/api/events", params={"limit": 5})
        assert r.status_code == 200
        data = r.json()
        assert len(data) > 0
        return f"{len(data)} events returned"

    def check_events_filter():
        r = httpx.get(f"{BASE}/api/events", params={"event_type": "market_crash", "limit": 5})
        assert r.status_code == 200
        data = r.json()
        return f"{len(data)} market crash events"

    results.append(check("GET /api/events", check_events))
    results.append(check("GET /api/events?event_type=market_crash", check_events_filter))

    # ── Sectors ─────────────────────────────────────────────
    header("SECTORS")

    def check_sectors():
        r = httpx.get(f"{BASE}/api/sectors")
        assert r.status_code == 200
        data = r.json()
        assert len(data) > 0
        return f"{len(data)} sectors"

    def check_sector_detail():
        r = httpx.get(f"{BASE}/api/sectors/technology")
        assert r.status_code == 200
        data = r.json()
        assert len(data) > 0
        return f"{len(data)} tech companies"

    results.append(check("GET /api/sectors", check_sectors))
    results.append(check("GET /api/sectors/technology", check_sector_detail))

    # ── Movers ──────────────────────────────────────────────
    header("MOVERS")

    def check_gainers():
        r = httpx.get(f"{BASE}/api/movers/gainers", params={"limit": 5})
        assert r.status_code == 200
        data = r.json()
        assert len(data) > 0
        top = data[0]
        return f"top gainer: {top['ticker']} +{top['pct_change']:.2f}%"

    def check_losers():
        r = httpx.get(f"{BASE}/api/movers/losers", params={"limit": 5})
        assert r.status_code == 200
        data = r.json()
        assert len(data) > 0
        top = data[0]
        return f"top loser: {top['ticker']} {top['pct_change']:.2f}%"

    results.append(check("GET /api/movers/gainers", check_gainers))
    results.append(check("GET /api/movers/losers", check_losers))

    # ── Heatmap ─────────────────────────────────────────────
    header("HEATMAP")

    def check_heatmap():
        r = httpx.get(f"{BASE}/api/heatmap")
        assert r.status_code == 200
        data = r.json()
        assert len(data) > 0
        top = data[0]
        return f"{len(data)} sectors, top: {top['display_name']} ({top['avg_pct_change']:+.2f}%)"

    results.append(check("GET /api/heatmap", check_heatmap))

    # ── AI Chat ─────────────────────────────────────────────
    header("AI CHAT")

    def check_chat():
        r = httpx.post(f"{BASE}/api/ai/chat", json={
            "question": "Why did NVIDIA rise in 2023?"
        })
        assert r.status_code == 200
        data = r.json()
        assert "question" in data
        assert "answer" in data
        return f"response received, sources={data['sources_used']}"

    results.append(check("POST /api/ai/chat", check_chat))

    # ── Swagger ─────────────────────────────────────────────
    header("DOCUMENTATION")

    def check_swagger():
        r = httpx.get(f"{BASE}/docs")
        assert r.status_code == 200
        return "Swagger UI accessible"

    results.append(check("GET /docs (Swagger UI)", check_swagger))

    # ── Summary ─────────────────────────────────────────────
    passed = sum(results)
    total = len(results)
    all_ok = passed == total

    print()
    print("=" * 62)
    if all_ok:
        print(f"  {BOLD}{PASS}  ALL {total} CHECKS PASSED — Phase 4 complete!{RESET}")
        print(f"  {BOLD}  Ready for Phase 5 — AI Integration{RESET}")
    else:
        print(f"  {BOLD}{FAIL}  {passed}/{total} checks passed — fix failures above{RESET}")
    print("=" * 62)
    print()

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
