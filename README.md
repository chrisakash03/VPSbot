# VPSbot

Telegram bot for natural-language reminders, recurring schedules, RSS monitoring, and a daily LLM-summarized news digest. Runs with **long polling** (no public URL required).

## Stack

- Python 3.12, [aiogram](https://docs.aiogram.dev/) 3.x
- APScheduler (`AsyncIOScheduler`) with SQLAlchemy job store
- SQLite via async SQLAlchemy (`aiosqlite`)
- `dateparser`, `feedparser`, OpenAI Python SDK (`gpt-5.6-luna`, low reasoning effort)

## Quick start (local)

1. Copy environment template and fill in values:

   ```bash
   cp .env.example .env
   ```

   Use a **separate test bot token** from [@BotFather](https://t.me/BotFather) for local development.

2. Run with Docker Compose (dev bind-mounts `src/` for live edits):

   ```bash
   docker compose up --build
   ```

3. In Telegram, talk to your bot:

   | Command | Description |
   |---------|-------------|
   | `/r <text>` | Create a reminder (natural language date/time) |
   | `/list` | List your upcoming reminders |
   | `/cancel` | Pick a reminder to delete (inline buttons) |
   | `/addfeed <url>` | Add RSS feed (admin only) |
   | `/removefeed <url\|id>` | Remove feed (admin) |
   | `/listfeeds` | List feeds (admin) |
   | `/digest on` / `/digest off` | Subscribe to daily digest |

Static feeds can also be listed in `feeds.yaml` (merged on startup).

## Configuration

See `.env.example` for all variables:

- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ADMIN_USER_ID`
- `OPENAI_API_KEY`
- `TIMEZONE` (IANA, e.g. `Asia/Singapore`) — parsing and display
- `DIGEST_TIME` (`HH:MM` local)
- `DIGEST_SEND_EMPTY` — if `true`, send a short message when no RSS items queued
- `RSS_POLL_INTERVAL_MINUTES`
- `DATABASE_PATH` — use `/data/bot.db` in Docker (named volume `bot_data`)

Times are stored in **UTC** internally and shown in your configured timezone.

## Tests

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest
```

Or inside Docker:

```bash
docker compose run --rm bot pytest
```

(For local pytest without Docker, set `DATABASE_PATH=./data/bot.db` in `.env` if you run the bot locally.)

## Project layout

```
src/vpsbot/
  bot/handlers/     # Telegram commands
  db/               # SQLAlchemy models
  reminders/        # NL parsing, recurrence, persistence
  scheduler/        # APScheduler + reload on startup
  rss/              # Feed poll, diff, queue, digest runner
  llm/              # OpenAI digest summarization (swappable)
  config.py         # dotenv settings
  main.py           # entrypoint (long polling)
```

## Deploy (Ubuntu VPS)

1. Clone the repo on the server and create `.env` (production token and secrets).
2. Build and run without source bind-mount:

   ```bash
   docker compose -f docker-compose.prod.yml up -d --build
   ```

3. Updates: `git pull` then re-run the same compose command.

The SQLite database persists in the `bot_data` Docker volume across restarts and image rebuilds.

## Scheduling notes

- One-off and recurring reminders are stored in SQLite; on startup the bot reloads pending jobs into APScheduler.
- Reminder fire times and actual send times are logged to `scheduler_audit` and application logs for drift checks.
- RSS items are queued in the database and summarized once per day at `DIGEST_TIME`.
