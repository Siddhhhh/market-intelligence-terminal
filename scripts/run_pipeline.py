"""
Market Intelligence Terminal — Pipeline Runner

Run individual pipeline steps or the daily update.

Usage:
    python scripts/run_pipeline.py stocks      # Full S&P 500 data download
    python scripts/run_pipeline.py crypto      # Crypto data download
    python scripts/run_pipeline.py macro       # Macro indicators download
    python scripts/run_pipeline.py events      # Run event detection
    python scripts/run_pipeline.py sectors     # Recompute sector performance
    python scripts/run_pipeline.py daily       # Daily incremental update (fast)
    python scripts/run_pipeline.py all         # Full pipeline (slow)
    python scripts/run_pipeline.py scheduler   # Start scheduler daemon
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger

VALID_COMMANDS = ["stocks", "crypto", "macro", "events", "sectors", "daily", "all", "scheduler"]


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in VALID_COMMANDS:
        print(f"\nUsage: python scripts/run_pipeline.py <command>")
        print(f"\nCommands:")
        print(f"  stocks      Full S&P 500 historical download (30-60 min)")
        print(f"  crypto      Crypto data download")
        print(f"  macro       Macroeconomic indicators")
        print(f"  events      Run event detection")
        print(f"  sectors     Recompute sector performance table")
        print(f"  daily       Daily incremental update (2-5 min)")
        print(f"  all         Full pipeline (stocks + crypto + macro + events)")
        print(f"  scheduler   Start the scheduler daemon (runs daily at 4:30 PM ET)")
        sys.exit(1)

    command = sys.argv[1]

    if command == "stocks":
        from backend.data_pipeline.stocks import ingest_sp500
        ingest_sp500()

    elif command == "crypto":
        from backend.data_pipeline.crypto import ingest_crypto
        ingest_crypto()

    elif command == "macro":
        from backend.data_pipeline.macro import ingest_macro
        ingest_macro()

    elif command == "events":
        from backend.data_pipeline.events import detect_all_events
        detect_all_events()

    elif command == "sectors":
        from backend.data_pipeline.sector_engine import compute_sector_performance
        compute_sector_performance()

    elif command == "daily":
        from backend.data_pipeline.daily_update import run_daily_update
        run_daily_update()

    elif command == "all":
        from backend.data_pipeline.stocks import ingest_sp500
        from backend.data_pipeline.crypto import ingest_crypto
        from backend.data_pipeline.macro import ingest_macro
        from backend.data_pipeline.events import detect_all_events
        ingest_sp500()
        ingest_crypto()
        ingest_macro()
        detect_all_events()

    elif command == "scheduler":
        from backend.data_pipeline.scheduler import run_standalone
        run_standalone()


if __name__ == "__main__":
    main()
