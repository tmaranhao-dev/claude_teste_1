"""Generate markdown and JSON output files from the digest result."""

import json
import logging
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from src.config import Settings
from src.summarizer import CopaDigestResult, DigestResult

logger = logging.getLogger(__name__)


def _get_output_path(
    output_dir: Path, date_str: str, ext: str, prefix: str = "digest"
) -> Path:
    """Get a unique output file path, appending -v2, -v3 etc. if needed."""
    base = output_dir / f"{prefix}-{date_str}{ext}"
    if not base.exists():
        return base

    version = 2
    while True:
        path = output_dir / f"{prefix}-{date_str}-v{version}{ext}"
        if not path.exists():
            return path
        version += 1


def write_digest(
    result: DigestResult | CopaDigestResult, settings: Settings
) -> tuple[Path, Path]:
    """Write the digest as markdown and JSON files. Returns (md_path, json_path)."""
    output_dir = settings.project_root / settings.delivery.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    date_str = result.date
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Markdown output via Jinja2
    templates_dir = settings.project_root / "templates"
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        keep_trailing_newline=True,
    )
    template = env.get_template(settings.template_name)

    template_vars = {
        "date": date_str,
        "editorial_note": result.editorial_note,
        "stories": result.stories,
        "generation_timestamp": now_str,
    }
    # Pass extra fields for Copa digest
    if hasattr(result, "numero_do_dia"):
        template_vars["numero_do_dia"] = result.numero_do_dia
    if hasattr(result, "proximos_eventos"):
        template_vars["proximos_eventos"] = result.proximos_eventos

    md_content = template.render(**template_vars)

    md_path = _get_output_path(output_dir, date_str, ".md", settings.output_prefix)
    md_path.write_text(md_content, encoding="utf-8")
    logger.info("Markdown digest written to %s", md_path)

    # JSON output
    json_data = asdict(result)
    json_data["generation_timestamp"] = now_str

    json_path = _get_output_path(output_dir, date_str, ".json", settings.output_prefix)
    json_path.write_text(
        json.dumps(json_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("JSON digest written to %s", json_path)

    return md_path, json_path
