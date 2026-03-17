"""
Market Intelligence Terminal — Setup Verification

Checks every required service and dependency before you proceed to Phase 2.

Run from project root:
    python scripts/verify_setup.py

Expected result: all checks pass.
"""

import sys
import subprocess
import os

# ── Formatting helpers ──────────────────────────────────────

PASS = "\033[92m✓ PASS\033[0m"
FAIL = "\033[91m✗ FAIL\033[0m"
BOLD = "\033[1m"
RESET = "\033[0m"


def header(title: str) -> None:
    print(f"\n{BOLD}── {title} ──{RESET}")


def result(name: str, passed: bool, detail: str = "") -> bool:
    status = PASS if passed else FAIL
    suffix = f"  ({detail})" if detail else ""
    print(f"  {status}  {name}{suffix}")
    return passed


# ── Individual checks ───────────────────────────────────────

def check_python_version() -> bool:
    v = sys.version_info
    ok = v.major == 3 and v.minor >= 10
    return result(
        "Python >= 3.10",
        ok,
        f"{v.major}.{v.minor}.{v.micro}",
    )


def check_env_file() -> bool:
    exists = os.path.isfile(".env")
    return result(
        ".env file exists",
        exists,
        "found" if exists else "copy .env.example to .env",
    )


def check_env_variables() -> bool:
    """Verify all critical env vars are loaded and non-empty."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        return result("Environment variables", False, "python-dotenv not installed")

    required = [
        "DATABASE_URL",
        "OLLAMA_BASE_URL",
        "LLM_ANALYST_MODEL",
        "LLM_ROUTER_MODEL",
    ]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        return result(
            "Environment variables",
            False,
            f"missing: {', '.join(missing)}",
        )
    return result(
        "Environment variables",
        True,
        "DATABASE_URL, OLLAMA_BASE_URL, LLM_ANALYST_MODEL, LLM_ROUTER_MODEL",
    )


def check_pydantic_settings() -> bool:
    """Verify settings load correctly through pydantic-settings."""
    try:
        sys.path.insert(0, os.getcwd())
        from config.settings import Settings
        s = Settings()
        ok = bool(s.database_url and s.ollama_base_url)
        return result(
            "Pydantic settings load",
            ok,
            f"analyst={s.llm_analyst_model}, router={s.llm_router_model}",
        )
    except Exception as e:
        return result("Pydantic settings load", False, str(e))


def check_postgres_connection() -> bool:
    """Connect to PostgreSQL using DATABASE_URL from .env."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
        from sqlalchemy import create_engine, text

        url = os.getenv("DATABASE_URL")
        if not url:
            return result("PostgreSQL connection", False, "DATABASE_URL not set")

        engine = create_engine(url, connect_args={"connect_timeout": 5})
        with engine.connect() as conn:
            row = conn.execute(text("SELECT version()")).scalar()
            version_short = row.split(",")[0] if row else "unknown"
        engine.dispose()
        return result("PostgreSQL connection", True, version_short)
    except Exception as e:
        return result("PostgreSQL connection", False, str(e)[:80])


def check_timescaledb() -> bool:
    """Verify TimescaleDB extension is installed in the target database."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
        from sqlalchemy import create_engine, text

        url = os.getenv("DATABASE_URL")
        if not url:
            return result("TimescaleDB extension", False, "DATABASE_URL not set")

        engine = create_engine(url, connect_args={"connect_timeout": 5})
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT extversion FROM pg_extension WHERE extname = 'timescaledb'")
            ).fetchone()
        engine.dispose()

        if row:
            return result("TimescaleDB extension", True, f"v{row[0]}")
        return result(
            "TimescaleDB extension",
            False,
            "extension not found — run: CREATE EXTENSION timescaledb;",
        )
    except Exception as e:
        return result("TimescaleDB extension", False, str(e)[:80])


def check_ollama_server() -> bool:
    """Verify Ollama API server is responding."""
    try:
        import httpx
        from dotenv import load_dotenv
        load_dotenv()

        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        resp = httpx.get(f"{base_url}/api/tags", timeout=5.0)
        if resp.status_code == 200:
            models = [m["name"] for m in resp.json().get("models", [])]
            return result(
                "Ollama server running",
                True,
                f"{len(models)} model(s) available",
            )
        return result("Ollama server running", False, f"HTTP {resp.status_code}")
    except Exception:
        # Fallback to subprocess if httpx not installed yet
        try:
            r = subprocess.run(
                ["ollama", "list"], capture_output=True, text=True, timeout=5
            )
            return result(
                "Ollama server running",
                r.returncode == 0,
                "responding (via CLI fallback)",
            )
        except Exception:
            return result(
                "Ollama server running",
                False,
                "cannot connect — run: ollama serve",
            )


def check_ollama_model(env_key: str, role: str) -> bool:
    """Verify a specific LLM model is pulled in Ollama."""
    from dotenv import load_dotenv
    load_dotenv()
    model_name = os.getenv(env_key, "")
    if not model_name:
        return result(f"LLM {role} model", False, f"{env_key} not set in .env")

    try:
        import httpx
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        resp = httpx.get(f"{base_url}/api/tags", timeout=5.0)
        if resp.status_code != 200:
            return result(f"LLM {role} model", False, "Ollama not responding")

        available = [m["name"].split(":")[0] for m in resp.json().get("models", [])]
        found = model_name in available
        detail = f"{model_name} found" if found else f"{model_name} NOT found — run: ollama pull {model_name}"
        return result(f"LLM {role} model", found, detail)
    except Exception:
        # Fallback without httpx
        try:
            r = subprocess.run(
                ["ollama", "list"], capture_output=True, text=True, timeout=5
            )
            found = model_name in r.stdout if r.returncode == 0 else False
            return result(f"LLM {role} model", found, f"{model_name} via CLI fallback")
        except Exception:
            return result(f"LLM {role} model", False, "cannot check — Ollama not available")


def check_node() -> bool:
    """Verify Node.js is installed."""
    try:
        r = subprocess.run(
            ["node", "--version"], capture_output=True, text=True, timeout=5
        )
        version = r.stdout.strip()
        major = int(version.lstrip("v").split(".")[0]) if version else 0
        return result("Node.js >= 18", r.returncode == 0 and major >= 18, version)
    except FileNotFoundError:
        return result("Node.js >= 18", False, "not found — install from nodejs.org")
    except Exception as e:
        return result("Node.js >= 18", False, str(e)[:80])


def check_key_packages() -> bool:
    """Verify all critical Python packages can be imported."""
    packages = {
        "fastapi": "API server",
        "uvicorn": "ASGI runner",
        "sqlalchemy": "ORM / database",
        "psycopg2": "PostgreSQL driver",
        "pandas": "data processing",
        "numpy": "numerical ops",
        "yfinance": "stock data",
        "pydantic_settings": "config management",
        "httpx": "HTTP client",
        "apscheduler": "job scheduler",
    }
    missing = []
    for pkg, purpose in packages.items():
        try:
            __import__(pkg)
        except ImportError:
            missing.append(f"{pkg} ({purpose})")

    if missing:
        return result(
            "Python packages",
            False,
            f"missing: {', '.join(missing)}",
        )
    return result(
        "Python packages",
        True,
        f"all {len(packages)} critical packages found",
    )


# ── Main ────────────────────────────────────────────────────

def main() -> None:
    print()
    print("=" * 62)
    print(f"  {BOLD}MARKET INTELLIGENCE TERMINAL — SETUP VERIFICATION{RESET}")
    print("=" * 62)

    results: list[bool] = []

    header("ENVIRONMENT")
    results.append(check_python_version())
    results.append(check_env_file())
    results.append(check_env_variables())
    results.append(check_pydantic_settings())
    results.append(check_key_packages())

    header("DATABASE")
    results.append(check_postgres_connection())
    results.append(check_timescaledb())

    header("AI ENGINE")
    results.append(check_ollama_server())
    results.append(check_ollama_model("LLM_ANALYST_MODEL", "analyst"))
    results.append(check_ollama_model("LLM_ROUTER_MODEL", "router"))

    header("FRONTEND")
    results.append(check_node())

    # ── Summary ─────────────────────────────────────────────
    passed = sum(results)
    total = len(results)
    all_ok = passed == total

    print()
    print("=" * 62)
    if all_ok:
        print(f"  {BOLD}{PASS}  ALL {total} CHECKS PASSED — Ready for Phase 2{RESET}")
    else:
        print(f"  {BOLD}{FAIL}  {passed}/{total} checks passed — fix failures above{RESET}")
    print("=" * 62)
    print()

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
