"""Scheduler for running the digest pipeline on a daily cron schedule."""

import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from src.config import Settings

logger = logging.getLogger(__name__)


def start_scheduler(run_pipeline: callable, settings: Settings) -> None:
    """Start a blocking scheduler that runs the pipeline daily."""
    scheduler = BlockingScheduler()

    trigger = CronTrigger(
        hour=settings.schedule.hour,
        minute=settings.schedule.minute,
        timezone=settings.schedule.timezone,
    )

    scheduler.add_job(
        run_pipeline,
        trigger=trigger,
        id="daily_digest",
        name="Daily News Digest",
        misfire_grace_time=3600,  # 1 hour grace period
    )

    logger.info(
        "Scheduler started. Digest will run daily at %02d:%02d (%s)",
        settings.schedule.hour,
        settings.schedule.minute,
        settings.schedule.timezone,
    )
    logger.info("Press Ctrl+C to stop.")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")
        scheduler.shutdown()
