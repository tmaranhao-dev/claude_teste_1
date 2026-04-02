#!/usr/bin/env python3
"""
Daily News Digest — Entry Point

Usage:
    python main.py --once       Run the digest pipeline once and exit
    python main.py --schedule   Start the scheduler (runs daily at configured time)
"""

import argparse
import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from src.config import load_settings
from src.curator import curate_candidates
from src.delivery import deliver_email
from src.fetcher import fetch_articles
from src.output import write_digest
from src.scheduler import start_scheduler
from src.summarizer import generate_digest

PROJECT_ROOT = Path(__file__).parent


def setup_logging(project_root: Path) -> None:
    """Configure logging to file and console."""
    logs_dir = project_root / "logs"
    logs_dir.mkdir(exist_ok=True)

    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

    # File handler with rotation (10MB, keep 30 files)
    file_handler = RotatingFileHandler(
        logs_dir / "digest.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=30,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(log_format))

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(log_format))

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


def run_pipeline() -> None:
    """Execute the full digest pipeline: fetch → curate → summarize → output → deliver."""
    logger = logging.getLogger("pipeline")
    logger.info("=" * 60)
    logger.info("Starting daily digest pipeline")

    try:
        settings = load_settings(PROJECT_ROOT)
    except (ValueError, FileNotFoundError) as e:
        logger.error("Configuration error: %s", e)
        return

    date_str = datetime.now().strftime("%Y-%m-%d")

    # Step 1: Fetch articles from RSS feeds
    try:
        articles = fetch_articles(settings)
        logger.info("Step 1/4: Fetched %d articles", len(articles))
    except RuntimeError as e:
        logger.error("Fetch failed: %s", e)
        return

    # Step 2: Curate candidates
    candidates = curate_candidates(articles, settings)
    logger.info("Step 2/4: Curated %d candidates", len(candidates))

    if not candidates:
        logger.error("No candidates after curation. Aborting.")
        return

    # Step 3: Generate digest via Claude API
    try:
        digest = generate_digest(candidates, settings, date_str)
        logger.info("Step 3/4: Generated digest with %d stories", len(digest.stories))
    except Exception as e:
        logger.error("Summarization failed: %s", e)
        return

    # Step 4: Write output files
    try:
        md_path, json_path = write_digest(digest, settings)
        logger.info("Step 4/4: Output written to %s", md_path.parent)
    except Exception as e:
        logger.error("Output generation failed: %s", e)
        return

    # Step 5: Deliver (email if configured via delivery.method or SMTP env vars)
    if settings.delivery.method in ("email", "both") or settings.smtp:
        deliver_email(md_path, json_path, settings)

    logger.info("Pipeline complete. Digest: %s", md_path.name)
    logger.info("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Daily News Digest for Creative Professionals"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run the digest pipeline once and exit",
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Start the scheduler (runs daily at configured time)",
    )

    args = parser.parse_args()

    if not args.once and not args.schedule:
        parser.print_help()
        print("\nPlease specify --once or --schedule")
        sys.exit(1)

    setup_logging(PROJECT_ROOT)
    logger = logging.getLogger("main")

    if args.once:
        logger.info("Running in single-run mode")
        run_pipeline()
    elif args.schedule:
        logger.info("Running in scheduler mode")
        try:
            settings = load_settings(PROJECT_ROOT)
        except (ValueError, FileNotFoundError) as e:
            logger.error("Configuration error: %s", e)
            sys.exit(1)
        start_scheduler(run_pipeline, settings)


if __name__ == "__main__":
    main()
