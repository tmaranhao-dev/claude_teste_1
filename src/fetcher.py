"""Fetch articles from RSS feeds with Google News fallback."""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import feedparser
import requests
from dateutil import parser as dateutil_parser

from src.config import Settings

logger = logging.getLogger(__name__)

FEEDPARSER_TIMEOUT = 15  # seconds
USER_AGENT = (
    "DigestDiario/1.0 (+https://github.com/digest-diario; news aggregator)"
)


@dataclass
class RawArticle:
    title: str
    source_name: str
    source_url: str
    link: str
    published: datetime | None
    summary: str
    language: str
    source_region: str  # "global" or "brazil"


def _parse_date(entry: dict) -> datetime | None:
    """Try to parse a date from a feed entry."""
    for field in ("published", "updated", "created"):
        raw = entry.get(field)
        if raw:
            try:
                return dateutil_parser.parse(raw)
            except (ValueError, OverflowError):
                continue
    return None


def _is_recent(dt: datetime | None, max_age_hours: int) -> bool:
    """Check if a datetime is within the allowed age window."""
    if dt is None:
        return True  # Keep articles with unknown dates
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    age_hours = (now - dt).total_seconds() / 3600
    return age_hours <= max_age_hours


def _fetch_single_feed(
    name: str, url: str, lang: str, region: str, max_age_hours: int
) -> list[RawArticle]:
    """Parse one RSS feed and return filtered articles."""
    try:
        feed = feedparser.parse(
            url,
            request_headers={"User-Agent": USER_AGENT},
        )
        if feed.bozo and not feed.entries:
            logger.warning("Feed '%s' returned errors: %s", name, feed.bozo_exception)
            return []
    except Exception as e:
        logger.warning("Failed to fetch feed '%s' (%s): %s", name, url, e)
        return []

    articles = []
    for entry in feed.entries:
        title = entry.get("title", "").strip()
        link = entry.get("link", "").strip()
        if not title or not link:
            continue

        pub_date = _parse_date(entry)
        if not _is_recent(pub_date, max_age_hours):
            continue

        summary = entry.get("summary", entry.get("description", ""))
        # Strip HTML tags from summary (basic)
        import re
        summary = re.sub(r"<[^>]+>", "", summary).strip()
        summary = summary[:500]  # Truncate long summaries

        articles.append(
            RawArticle(
                title=title,
                source_name=name,
                source_url=url,
                link=link,
                published=pub_date,
                summary=summary,
                language=lang,
                source_region=region,
            )
        )

    logger.info("Feed '%s': fetched %d articles", name, len(articles))
    return articles


def _fetch_google_news_fallback(
    queries: list[str], max_age_hours: int
) -> list[RawArticle]:
    """Fallback: search Google News RSS for additional articles."""
    articles = []
    seen_links = set()

    for query in queries:
        url = (
            f"https://news.google.com/rss/search?"
            f"q={requests.utils.quote(query)}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
        )
        try:
            feed = feedparser.parse(
                url,
                request_headers={"User-Agent": USER_AGENT},
            )
        except Exception as e:
            logger.warning("Google News fallback failed for '%s': %s", query, e)
            continue

        for entry in feed.entries[:5]:  # Limit per query
            link = entry.get("link", "").strip()
            if not link or link in seen_links:
                continue
            seen_links.add(link)

            pub_date = _parse_date(entry)
            if not _is_recent(pub_date, max_age_hours):
                continue

            title = entry.get("title", "").strip()
            source_tag = entry.get("source", {})
            source_name = (
                source_tag.get("title", "Google News")
                if isinstance(source_tag, dict)
                else "Google News"
            )

            articles.append(
                RawArticle(
                    title=title,
                    source_name=source_name,
                    source_url=link,
                    link=link,
                    published=pub_date,
                    summary=entry.get("summary", "")[:500],
                    language="pt-br",
                    source_region="brazil",
                )
            )

    logger.info("Google News fallback: fetched %d articles", len(articles))
    return articles


def fetch_articles(settings: Settings) -> list[RawArticle]:
    """Fetch articles from all configured RSS feeds with fallback."""
    all_articles: list[RawArticle] = []
    seen_links: set[str] = set()
    feed_failures = 0
    total_feeds = len(settings.sources_global) + len(settings.sources_brazil)

    # Fetch global sources
    for source in settings.sources_global:
        articles = _fetch_single_feed(
            source.name, source.url, source.lang, "global",
            settings.max_feed_age_hours,
        )
        if not articles:
            feed_failures += 1
        for a in articles:
            if a.link not in seen_links:
                seen_links.add(a.link)
                all_articles.append(a)

    # Fetch Brazilian sources
    for source in settings.sources_brazil:
        articles = _fetch_single_feed(
            source.name, source.url, source.lang, "brazil",
            settings.max_feed_age_hours,
        )
        if not articles:
            feed_failures += 1
        for a in articles:
            if a.link not in seen_links:
                seen_links.add(a.link)
                all_articles.append(a)

    logger.info(
        "RSS feeds: %d articles from %d/%d feeds",
        len(all_articles), total_feeds - feed_failures, total_feeds,
    )

    # Fallback if we don't have enough candidates
    min_candidates = settings.num_stories * 3
    if len(all_articles) < min_candidates:
        logger.info(
            "Only %d articles (need %d). Triggering Google News fallback.",
            len(all_articles), min_candidates,
        )
        fallback = _fetch_google_news_fallback(
            settings.fallback_search_queries, settings.max_feed_age_hours
        )
        for a in fallback:
            if a.link not in seen_links:
                seen_links.add(a.link)
                all_articles.append(a)

    if not all_articles:
        raise RuntimeError(
            "No articles fetched from any source. "
            "Check your internet connection and feed URLs in config.json."
        )

    logger.info("Total articles fetched: %d", len(all_articles))
    return all_articles
