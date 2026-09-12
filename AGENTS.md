# AGENTS.md — mrz-qqbot

## Project

QQ group chat bot built on **NoneBot2** + OneBot v11 adapter + **NapCat**. Python >= 3.10 (3.12 in Docker).

## Architecture

```
bot.py              # Entry point — loads NoneBot2, registers OneBot v11 adapter
src/plugins/        # Plugin directory (loaded via pyproject.toml [tool.nonebot])
  websearch/        # DuckDuckGo + Bing search (also used as a library)
  htmlrender/       # Playwright-based HTML/MD-to-image rendering
  imagerender/      # text2pic / md2pic / html2pic commands
  namelist/         # Blacklist/whitelist (SUPERUSER-only, event_preprocessor drops blocked msgs)
  members/          # Group member tracking + /member list rendering
  jrrp/             # Daily luck (/jrrp) + sleep keywords
  alipayvoice/      # Alipay voice memo (/alipay)
  ping/             # Minecraft server query (/mc)
  welcome/          # Random join messages
  restart/          # Bot restart command
  nonebot-plugin-apscheduler/  # APScheduler integration
  nonebot-plugin-status/       # Status/health check
napcat/             # NapCat (QQ client) config for Docker
data/               # Runtime data (member lists, chat history, memory)
```

## Commands

```bash
./start.sh              # Auto-creates .venv, installs deps, runs bot locally
./start.sh docker       # Start with docker compose
./start.sh stop         # docker compose down
./start.sh logs         # docker compose logs -f
python bot.py           # Run directly (need .venv activated)
rebuild-bot.sh          # docker compose down bot && up bot -d --build
```

Dependencies are auto-installed by `start.sh` (pip + playwright chromium).

## Environment

- **`.env`** — Main config (gitignored, see `.env.example`). NoneBot2 auto-loads these as snake_case config.
- **`.env.prod`** — Prod override (gitignored).
- **`.env.docker`** — Only `QQ_ACCOUNT` for NapCat login.
- Key env vars: `WEB_SEARCH_BACKEND`.

## Docker

- Two services: `napcat` (QQ client, port 6099) and `bot` (NoneBot2, port 6060).
- Bot connects to NapCat via WebSocket: `ws://bot:6060/onebot/v11/ws`.
- NapCat WebUI at `http://localhost:6099` — scan QR code to login QQ.
- Bot mounts `./data:/app/data` and `./src:/app/src` for live reload in Docker.
- The Dockerfile installs `trafatura` (not in pyproject.toml) for HTML extraction.

## Key Quirks

- **No test suite** — no pytest, no tests directory.
- **No linting/typecheck** — no ruff, mypy, or similar config.
- **Playwright Chromium** required for htmlrender. Installed in Dockerfile + start.sh. Local dev: `playwright install chromium`.
- **COMMAND_START=[""]** — commands don't need a prefix (e.g. `/mc` is literally `/mc`).
- **namelist plugin** silently drops messages from blocked users via `event_preprocessor` + `IgnoredException`.
- **`data/member/*.json`** is gitignored — populated at runtime by the members plugin.
- **websearch** is both a command handler and an importable library (other plugins call `web_search()`).
