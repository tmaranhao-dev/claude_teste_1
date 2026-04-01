"""Filter, score, and select the best article candidates for the digest."""

import logging
import re
from datetime import datetime, timezone

from src.config import Settings
from src.fetcher import RawArticle

logger = logging.getLogger(__name__)


def _normalize(text: str) -> set[str]:
    """Normalize text into a set of lowercase words for comparison."""
    return set(re.findall(r"\w+", text.lower()))


def _jaccard_similarity(a: set[str], b: set[str]) -> float:
    """Compute Jaccard similarity between two word sets."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _deduplicate(articles: list[RawArticle], threshold: float = 0.7) -> list[RawArticle]:
    """Remove articles with very similar titles."""
    unique: list[RawArticle] = []
    seen_titles: list[set[str]] = []

    for article in articles:
        words = _normalize(article.title)
        is_duplicate = any(
            _jaccard_similarity(words, seen) >= threshold
            for seen in seen_titles
        )
        if not is_duplicate:
            unique.append(article)
            seen_titles.append(words)

    removed = len(articles) - len(unique)
    if removed:
        logger.info("Deduplication removed %d articles", removed)
    return unique


def _recency_score(published: datetime | None) -> float:
    """Score article freshness: today=1.0, yesterday=0.7, older=0.4."""
    if published is None:
        return 0.5  # Unknown date gets a neutral score
    now = datetime.now(timezone.utc)
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    age_hours = (now - published).total_seconds() / 3600
    if age_hours <= 24:
        return 1.0
    elif age_hours <= 48:
        return 0.7
    return 0.4


def _relevance_score(article: RawArticle, settings: Settings) -> float:
    """Score article relevance based on keyword matches with focus areas."""
    text = f"{article.title} {article.summary}".lower()
    matches = 0
    areas_matched = 0

    for area in settings.focus_areas:
        area_hit = False
        for keyword in area.keywords:
            if keyword.lower() in text:
                matches += 1
                area_hit = True
        if area_hit:
            areas_matched += 1

    # Reward covering multiple focus areas
    if areas_matched == 0:
        return 0.1
    return min(1.0, 0.3 + (matches * 0.1) + (areas_matched * 0.15))


def _region_bonus(article: RawArticle) -> float:
    """Give a small bonus to Brazilian articles to ensure representation."""
    return 0.2 if article.source_region == "brazil" else 0.0


def curate_candidates(
    articles: list[RawArticle], settings: Settings
) -> list[RawArticle]:
    """Select the best candidates for Claude to curate the final digest."""
    # Step 1: Deduplicate
    articles = _deduplicate(articles)

    # Step 2: Score each article
    scored: list[tuple[float, RawArticle]] = []
    for article in articles:
        score = (
            _recency_score(article.published) * 0.4
            + _relevance_score(article, settings) * 0.4
            + _region_bonus(article) * 0.2
        )
        scored.append((score, article))

    # Step 3: Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)

    # Step 4: Ensure minimum Brazilian candidates
    min_brazil = settings.min_brazil_stories * 2
    brazil_count = sum(
        1 for _, a in scored[:15] if a.source_region == "brazil"
    )

    result: list[RawArticle] = []
    brazil_added = 0

    if brazil_count < min_brazil:
        # First, add top Brazilian articles
        brazil_articles = [(s, a) for s, a in scored if a.source_region == "brazil"]
        for _, article in brazil_articles[:min_brazil]:
            result.append(article)
            brazil_added += 1

        # Then fill with remaining top articles
        brazil_links = {a.link for a in result}
        for _, article in scored:
            if article.link not in brazil_links:
                result.append(article)
            if len(result) >= 15:
                break
    else:
        result = [a for _, a in scored[:15]]
        brazil_added = sum(1 for a in result if a.source_region == "brazil")

    logger.info(
        "Curated %d candidates (%d Brazilian) from %d total",
        len(result), brazil_added, len(articles),
    )
    return result
