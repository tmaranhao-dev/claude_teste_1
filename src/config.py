"""Configuration loader for the daily news digest system."""
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv


@dataclass
class FocusArea:
    id: str
    name: str
    keywords: list[str]


@dataclass
class Source:
    name: str
    url: str
    lang: str


@dataclass
class DeliveryConfig:
    method: str
    output_dir: str


@dataclass
class ScheduleConfig:
    hour: int
    minute: int
    timezone: str


@dataclass
class SmtpConfig:
    host: str
    port: int
    user: str
    password: str
    recipients: list[str]


@dataclass
class Settings:
    anthropic_api_key: str
    num_stories: int
    min_brazil_stories: int
    language: str
    max_feed_age_hours: int
    claude_model: str
    focus_areas: list[FocusArea]
    sources_global: list[Source]
    sources_brazil: list[Source]
    fallback_search_queries: list[str]
    delivery: DeliveryConfig
    schedule: ScheduleConfig
    digest_type: str = "general"
    output_prefix: str = "digest"
    template_name: str = "digest.md.j2"
    email_subject_prefix: str = "Digest Diário"
    smtp: SmtpConfig | None = None
    project_root: Path = field(default_factory=lambda: Path.cwd())


def load_settings(project_root: Path | None = None, config_path: Path | None = None) -> Settings:
    """Load settings from .env and config.json files."""
    if project_root is None:
        project_root = Path(__file__).parent.parent

    env_path = project_root / ".env"
    if config_path is None:
        config_path = project_root / "config.json"
    elif not config_path.is_absolute():
        config_path = project_root / config_path

    load_dotenv(env_path)

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY not found. "
            "Copy .env.example to .env and set your API key."
        )

    if not config_path.exists():
        raise FileNotFoundError(f"config.json not found at {config_path}")

    with open(config_path) as f:
        cfg = json.load(f)

    focus_areas = [
        FocusArea(id=fa["id"], name=fa["name"], keywords=fa["keywords"])
        for fa in cfg["focus_areas"]
    ]
    sources_global = [
        Source(name=s["name"], url=s["url"], lang=s["lang"])
        for s in cfg["sources"]["global"]
    ]
    sources_brazil = [
        Source(name=s["name"], url=s["url"], lang=s["lang"])
        for s in cfg.get("sources", {}).get("brazil", [])
    ]
    delivery = DeliveryConfig(
        method=cfg["delivery"]["method"],
        output_dir=cfg["delivery"]["output_dir"],
    )
    schedule = ScheduleConfig(
        hour=cfg["schedule"]["hour"],
        minute=cfg["schedule"]["minute"],
        timezone=cfg["schedule"]["timezone"],
    )

    smtp = None
    smtp_host = os.getenv("SMTP_HOST")
    if smtp_host:
        recipients_raw = os.getenv("EMAIL_TO", "")
        smtp = SmtpConfig(
            host=smtp_host,
            port=int(os.getenv("SMTP_PORT", "587")),
            user=os.getenv("SMTP_USER", ""),
            password=os.getenv("SMTP_PASSWORD", ""),
            recipients=[r.strip() for r in recipients_raw.split(",") if r.strip()],
        )

    return Settings(
        anthropic_api_key=api_key,
        num_stories=cfg.get("num_stories", 5),
        min_brazil_stories=cfg.get("min_brazil_stories", 2),
        language=cfg.get("language", "pt-br"),
        max_feed_age_hours=cfg.get("max_feed_age_hours", 48),
        claude_model=cfg.get("claude_model", "claude-sonnet-4-20250514"),
        focus_areas=focus_areas,
        sources_global=sources_global,
        sources_brazil=sources_brazil,
        fallback_search_queries=cfg.get("fallback_search_queries", []),
        delivery=delivery,
        schedule=schedule,
        digest_type=cfg.get("digest_type", "general"),
        output_prefix=cfg.get("output_prefix", "digest"),
        template_name=cfg.get("template_name", "digest.md.j2"),
        email_subject_prefix=cfg.get("email_subject_prefix", "Digest Diário"),
        smtp=smtp,
        project_root=project_root,
    )
