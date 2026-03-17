"""
Market Intelligence Terminal — Daily Scheduler

Uses APScheduler to automatically run the daily update pipeline
after US market close (default: 4:30 PM ET).

Run modes:
    1. Standalone daemon:
        python -m backend.data_pipeline.scheduler

    2. Integrated with API server (add to main.py startup)

    3. Manual trigger:
        python scripts/run_pipeline.py daily

Configuration via .env:
    SCHEDULER_ENABLED=true
    SCHEDULER_HOUR=16
    SCHEDULER_MINUTE=30
"""

import sys
import os
import signal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger
from datetime import datetime

from config import settings


def daily_job():
    """The actual job that runs daily."""
    logger.info("=" * 60)
    logger.info(f"  SCHEDULED JOB STARTED: {datetime.now()}")
    logger.info("=" * 60)

    try:
        from backend.data_pipeline.daily_update import run_daily_update
        result = run_daily_update()

        logger.info("=" * 60)
        logger.info(f"  SCHEDULED JOB COMPLETED SUCCESSFULLY")
        logger.info(f"  Results: {result}")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"SCHEDULED JOB FAILED: {e}")


def create_scheduler(background: bool = False) -> BlockingScheduler | BackgroundScheduler:
    """
    Create and configure the scheduler.

    Args:
        background: If True, use BackgroundScheduler (non-blocking, for API integration).
                    If False, use BlockingScheduler (standalone daemon).
    """
    SchedulerClass = BackgroundScheduler if background else BlockingScheduler
    scheduler = SchedulerClass(timezone="US/Eastern")

    # Daily update job — runs Mon-Fri at configured time (default 4:30 PM ET)
    trigger = CronTrigger(
        day_of_week="mon-fri",
        hour=settings.scheduler_hour,
        minute=settings.scheduler_minute,
        timezone="US/Eastern",
    )

    scheduler.add_job(
        daily_job,
        trigger=trigger,
        id="daily_market_update",
        name="Daily Market Data Update",
        replace_existing=True,
        misfire_grace_time=3600,  # Allow 1 hour grace period if missed
    )

    logger.info(
        f"Scheduler configured: daily update at "
        f"{settings.scheduler_hour:02d}:{settings.scheduler_minute:02d} ET (Mon-Fri)"
    )

    return scheduler


def start_background_scheduler() -> BackgroundScheduler:
    """
    Start a background scheduler (non-blocking).
    Use this when integrating with the API server.
    """
    if not settings.scheduler_enabled:
        logger.info("Scheduler is disabled (SCHEDULER_ENABLED=false)")
        return None

    scheduler = create_scheduler(background=True)
    scheduler.start()
    logger.info("Background scheduler started")
    return scheduler


def run_standalone():
    """
    Run the scheduler as a standalone daemon process.
    Blocks until interrupted with Ctrl+C.
    """
    logger.info("=" * 60)
    logger.info("  MARKET INTELLIGENCE — SCHEDULER DAEMON")
    logger.info(f"  Schedule: {settings.scheduler_hour:02d}:{settings.scheduler_minute:02d} ET, Mon-Fri")
    logger.info(f"  Enabled: {settings.scheduler_enabled}")
    logger.info("=" * 60)

    if not settings.scheduler_enabled:
        logger.warning("Scheduler is disabled. Set SCHEDULER_ENABLED=true in .env")
        return

    scheduler = create_scheduler(background=False)

    # Handle graceful shutdown
    def shutdown(signum, frame):
        logger.info("Shutting down scheduler...")
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    logger.info("Scheduler running. Press Ctrl+C to stop.")
    logger.info(f"Next run: check scheduler logs for next trigger time")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    run_standalone()
