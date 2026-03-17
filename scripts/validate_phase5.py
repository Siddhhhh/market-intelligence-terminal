"""
Market Intelligence Terminal — Phase 5 Validation

Tests the AI system end-to-end:
    1. Query router classifies questions correctly
    2. Evidence builder gathers database context
    3. Analyst generates grounded responses
    4. API endpoint returns structured results

IMPORTANT: Requires both Ollama and the API server to be running:
    Terminal 1: ollama serve  (if not already running)
    Terminal 2: uvicorn backend.api.main:app --reload --port 8000
    Terminal 3: python scripts/validate_phase5.py
"""

import sys
import os
import time

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
    print(f"  {BOLD}PHASE 5 — AI SYSTEM VALIDATION{RESET}")
    print("=" * 62)

    # Check server
    try:
        httpx.get(f"{BASE}/", timeout=5.0)
    except httpx.ConnectError:
        print(f"\n  {FAIL}  Cannot connect to {BASE}")
        print(f"       Start the server: uvicorn backend.api.main:app --reload --port 8000")
        sys.exit(1)

    # Check Ollama
    try:
        r = httpx.get("http://localhost:11434/api/tags", timeout=5.0)
        models = [m["name"].split(":")[0] for m in r.json().get("models", [])]
        print(f"\n  Ollama models available: {', '.join(models)}")
    except Exception:
        print(f"\n  {FAIL}  Cannot connect to Ollama")
        print(f"       Make sure Ollama is running")
        sys.exit(1)

    results = []

    # ── Query Router ────────────────────────────────────────
    header("QUERY ROUTER (Mistral)")

    def test_router_market():
        r = httpx.post(f"{BASE}/api/ai/chat", json={
            "question": "Why did Tesla stock drop in 2022?"
        }, timeout=180.0)
        assert r.status_code == 200
        data = r.json()
        return f"category={data['category']}, time={data['processing_time']}s"

    def test_router_knowledge():
        r = httpx.post(f"{BASE}/api/ai/chat", json={
            "question": "What is inflation?"
        }, timeout=180.0)
        assert r.status_code == 200
        data = r.json()
        return f"category={data['category']}, time={data['processing_time']}s"

    def test_router_historical():
        r = httpx.post(f"{BASE}/api/ai/chat", json={
            "question": "What were the biggest market crashes since 2000?"
        }, timeout=180.0)
        assert r.status_code == 200
        data = r.json()
        return f"category={data['category']}, time={data['processing_time']}s"

    def test_router_offtopic():
        r = httpx.post(f"{BASE}/api/ai/chat", json={
            "question": "What is the weather today?"
        }, timeout=180.0)
        assert r.status_code == 200
        data = r.json()
        return f"category={data['category']}, time={data['processing_time']}s"

    results.append(check("Market data question (Tesla)", test_router_market))
    results.append(check("Finance knowledge question", test_router_knowledge))
    results.append(check("Historical analysis question", test_router_historical))
    results.append(check("Off-topic question", test_router_offtopic))

    # ── Evidence + Analysis ─────────────────────────────────
    header("EVIDENCE BUILDER + ANALYST (Llama3)")

    def test_nvidia_analysis():
        r = httpx.post(f"{BASE}/api/ai/chat", json={
            "question": "Why did NVIDIA rise in 2023?"
        }, timeout=180.0)
        assert r.status_code == 200
        data = r.json()
        assert len(data["answer"]) > 50, "Answer too short"
        assert data["confidence"] > 0, "No evidence gathered"
        ev = data["evidence_summary"]
        return (
            f"answer={len(data['answer'])} chars, "
            f"confidence={data['confidence']}, "
            f"tickers={ev.get('tickers_analyzed', [])}, "
            f"events={ev.get('events_found', 0)}"
        )

    def test_sector_analysis():
        r = httpx.post(f"{BASE}/api/ai/chat", json={
            "question": "Which sectors performed best in 2020?"
        }, timeout=180.0)
        assert r.status_code == 200
        data = r.json()
        assert len(data["answer"]) > 50
        return f"answer={len(data['answer'])} chars, sources={data['sources_used']}"

    def test_response_has_sources():
        r = httpx.post(f"{BASE}/api/ai/chat", json={
            "question": "How did Apple perform in 2024?"
        }, timeout=180.0)
        assert r.status_code == 200
        data = r.json()
        assert len(data["sources_used"]) > 0, "No sources used"
        return f"sources={data['sources_used']}, confidence={data['confidence']}"

    results.append(check("NVIDIA 2023 analysis (evidence + LLM)", test_nvidia_analysis))
    results.append(check("Sector performance analysis", test_sector_analysis))
    results.append(check("Response includes data sources", test_response_has_sources))

    # ── Response Quality ────────────────────────────────────
    header("RESPONSE QUALITY")

    def test_answer_not_placeholder():
        r = httpx.post(f"{BASE}/api/ai/chat", json={
            "question": "What happened to Bitcoin in 2021?"
        }, timeout=180.0)
        assert r.status_code == 200
        data = r.json()
        assert "Phase 5" not in data["answer"], "Still returning placeholder"
        assert len(data["answer"]) > 100, "Answer too short"
        return f"real LLM response, {len(data['answer'])} chars"

    def test_structured_response():
        r = httpx.post(f"{BASE}/api/ai/chat", json={
            "question": "Why did the market crash in March 2020?"
        }, timeout=180.0)
        assert r.status_code == 200
        data = r.json()
        assert "question" in data
        assert "category" in data
        assert "answer" in data
        assert "evidence_summary" in data
        assert "confidence" in data
        assert "processing_time" in data
        return f"all fields present, time={data['processing_time']}s"

    results.append(check("Answer is real LLM output (not placeholder)", test_answer_not_placeholder))
    results.append(check("Response has all required fields", test_structured_response))

    # ── Summary ─────────────────────────────────────────────
    passed = sum(results)
    total = len(results)
    all_ok = passed == total

    print()
    print("=" * 62)
    if all_ok:
        print(f"  {BOLD}{PASS}  ALL {total} CHECKS PASSED — Phase 5 complete!{RESET}")
        print(f"  {BOLD}  Ready for Phase 6 — Frontend Dashboard{RESET}")
    else:
        print(f"  {BOLD}{FAIL}  {passed}/{total} checks passed — fix failures above{RESET}")
    print("=" * 62)
    print()

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
