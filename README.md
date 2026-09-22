# VPSbot

Telegram bot for natural-language reminders, recurring schedules, RSS monitoring, and a daily LLM-summarized news digest. Runs with **long polling** (no public URL required).

## Stack

- Python 3.12, [aiogram](https://docs.aiogram.dev/) 3.x
- APScheduler (`AsyncIOScheduler`) with SQLAlchemy job store
- SQLite via async SQLAlchemy (`aiosqlite`)
- `dateparser`, `feedparser`, OpenAI Python SDK (`gpt-5.6-luna`, low reasoning effort)
- Optional [TypeSafe Jev](https://docs.typesafe.ai/introduction) for complex reminder schedules

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
   | `/digest on` / `/digest off` | Enable daily digest in the configured group (admin) |
   | `/chatid` | Show this chat’s ID (admin; use for `DIGEST_GROUP_CHAT_ID`) |

Static feeds can also be listed in `feeds.yaml` (merged on startup).

### Groups

1. Add the bot to your group. Keep **privacy mode enabled** in [@BotFather](https://t.me/BotFather) (`/setprivacy`) unless you need the bot to read every message.
2. With privacy on, the bot receives **commands**, **@mentions**, and **replies** to its messages.
3. Set a reminder: `@YourBot remind me tomorrow at 9am` or `/r@YourBot …`
4. Add **`/pm`** in the text to receive the notification in **DM** (you must `/start` the bot in private first).
5. Reminders default to posting in the **group**; `/list` and `/cancel` are per user.
6. Set `DIGEST_GROUP_CHAT_ID` in `.env` (use `/chatid` in the target group). Admin runs `/digest on` **in that group only**.
7. RSS feed commands (`/addfeed`, etc.) work in **DM only**.

## Configuration

See `.env.example` for all variables:

- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ADMIN_USER_ID`
- `OPENAI_API_KEY`
- `TIMEZONE` (IANA, e.g. `Asia/Singapore`) — parsing and display
- `DIGEST_TIME` (`HH:MM` local)
- `DIGEST_SEND_EMPTY` — if `true`, send a short message when no RSS items queued
- `RSS_POLL_INTERVAL_MINUTES`
- `DATABASE_PATH` — use `/data/bot.db` in Docker (named volume `bot_data`)
- `DIGEST_GROUP_CHAT_ID` — supergroup id for the single daily digest channel

Times are stored in **UTC** internally and shown in your configured timezone.

### Complex reminders (Jev)

Simple `/r` phrases use **dateparser + regex** (fast, no API). Complex patterns (e.g. `every 2 days at 8pm for 2 weeks`) trigger **Jev** when `JEV_ENABLED=true` and `TYPESAFE_API_KEY` is set.

- Confidence ≥ `JEV_CONFIDENCE_AUTO` → schedule immediately
- Between `JEV_CONFIDENCE_MIN` and auto → inline **confirm**
- Below min → ask to rephrase

Fire times and recurrence are always computed in Python (`schedule_spec`, `recurrence.py`), not by the model.

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
- **Missed while offline:** on startup, any overdue active reminder is sent once (`Reminder (delayed): …`). One-offs are then deactivated; recurring reminders advance to the next occurrence (not every missed slot).
- **Retention:** inactive reminder rows and old `scheduler_audit` entries are purged on startup (`REMINDER_RETENTION_DAYS`, `SCHEDULER_AUDIT_RETENTION_DAYS` in `.env`; `0` = disable).
- Reminder fire times and actual send times are logged to `scheduler_audit` and application logs for drift checks.
- RSS items are queued in the database and summarized once per day at `DIGEST_TIME`.
