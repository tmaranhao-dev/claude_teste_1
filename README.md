# Digest Diário — Daily News Digest for Creative Professionals

Sistema automatizado de curadoria diária de notícias para profissionais brasileiros de comunicação, criatividade e produção audiovisual.

Fetches articles from RSS feeds (global + Brazilian sources), uses Claude AI to curate and summarize the top stories, and outputs structured markdown + JSON files ready for newsletter, LinkedIn, and Instagram repurposing.

## Features

- **Automated RSS fetching** from 14+ sources (global and Brazilian)
- **AI-powered curation** via Claude API — selects and analyzes the most relevant stories
- **Brazilian lens** — at least 2 stories with direct relevance to the Brazilian market
- **Dual output** — dated markdown file + structured JSON for automation
- **Email delivery** — optional SMTP delivery with JSON attachment
- **Daily scheduling** — runs at 7am São Paulo time (configurable)
- **Fully configurable** — sources, focus areas, language, delivery method, schedule

## Quick Start

### 1. Prerequisites

- Python 3.10+
- A [Claude API key](https://console.anthropic.com/)

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure

Copy the environment template and add your API key:

```bash
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY
```

Review and customize `config.json` to adjust:
- Number of stories (`num_stories`)
- Minimum Brazilian stories (`min_brazil_stories`)
- Output language (`language`: `"pt-br"` or `"en"`)
- RSS sources (add/remove feeds)
- Focus areas and keywords
- Delivery method (`"local"`, `"email"`, or `"both"`)
- Schedule time and timezone

### 4. Run

**Single run** (generate today's digest):
```bash
python main.py --once
```

**Scheduled mode** (runs daily at configured time):
```bash
python main.py --schedule
```

**Alternative: system cron** (if you prefer not to keep a process running):
```bash
# Add to crontab (crontab -e):
0 10 * * * cd /path/to/project && /path/to/python main.py --once
# Note: cron uses UTC. 10:00 UTC = 07:00 BRT (UTC-3)
```

## Output

Each run produces two files in the `output/` directory:

- `digest-YYYY-MM-DD.md` — formatted markdown digest
- `digest-YYYY-MM-DD.json` — structured JSON data

### Markdown format

Each story includes:
- **O que aconteceu** — factual summary (2-3 sentences)
- **Por que importa** — analytical, opinionated take for creative professionals
- **Ângulo brasileiro** — how it connects to the Brazilian market
- **Ângulo de conteúdo** — suggested angle for newsletter/LinkedIn/Instagram content

## Email Delivery

To enable email delivery, set these in `.env`:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EMAIL_TO=recipient1@example.com,recipient2@example.com
```

And set `"method": "email"` (or `"both"`) in `config.json` under `delivery`.

For Gmail, use an [App Password](https://support.google.com/accounts/answer/185833) instead of your regular password.

## Configuration Reference

### config.json

| Field | Default | Description |
|-------|---------|-------------|
| `num_stories` | 5 | Number of stories in each digest |
| `min_brazil_stories` | 2 | Minimum stories with Brazilian relevance |
| `language` | `"pt-br"` | Output language (`"pt-br"` or `"en"`) |
| `max_feed_age_hours` | 48 | Maximum article age to consider |
| `claude_model` | `"claude-sonnet-4-20250514"` | Claude model for summarization |
| `sources.global` | 8 feeds | Global RSS sources |
| `sources.brazil` | 6 feeds | Brazilian RSS sources |
| `delivery.method` | `"local"` | `"local"`, `"email"`, or `"both"` |
| `delivery.output_dir` | `"output"` | Local output directory |
| `schedule.hour` | 7 | Hour to run (in configured timezone) |
| `schedule.minute` | 0 | Minute to run |
| `schedule.timezone` | `"America/Sao_Paulo"` | Timezone for scheduling |

### .env

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude API key |
| `SMTP_HOST` | For email | SMTP server hostname |
| `SMTP_PORT` | For email | SMTP port (default: 587) |
| `SMTP_USER` | For email | SMTP username |
| `SMTP_PASSWORD` | For email | SMTP password |
| `EMAIL_TO` | For email | Comma-separated recipient emails |

## Logs

Logs are written to `logs/digest.log` with automatic rotation (10MB, 30 files kept). Console output shows INFO level; the log file captures DEBUG level for troubleshooting.

## Project Structure

```
├── main.py              # Entry point (--once or --schedule)
├── config.json          # Content preferences and source configuration
├── .env                 # API keys and SMTP credentials (not in git)
├── requirements.txt     # Python dependencies
├── src/
│   ├── config.py        # Settings loader
│   ├── fetcher.py       # RSS feed parser with fallback
│   ├── curator.py       # Article filtering and scoring
│   ├── summarizer.py    # Claude API integration
│   ├── output.py        # Markdown + JSON file generation
│   ├── delivery.py      # Email delivery via SMTP
│   └── scheduler.py     # APScheduler daily cron
├── templates/
│   └── digest.md.j2     # Jinja2 template for markdown output
├── output/              # Generated digests (gitignored)
└── logs/                # Application logs (gitignored)
```
