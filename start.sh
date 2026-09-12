#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

case "${1:-}" in
  docker|d)
    echo "[*] Starting with Docker..."
    if [ ! -f ".env.docker" ]; then
      echo "[!] Please create .env.docker with your QQ account first."
      exit 1
    fi
    export $(grep -v '^#' .env.docker | xargs)
    if [ -z "$QQ_ACCOUNT" ]; then
      echo "[!] Please set QQ_ACCOUNT in .env.docker"
      exit 1
    fi
    # 生成 NapCat OneBot 配置
    mkdir -p napcat/config
    cat > "napcat/config/onebot11_${QQ_ACCOUNT}.json" <<'CONF'
{
  "network": {
    "websocketClients": [
      {
        "enable": true,
        "url": "ws://bot:6060/onebot/v11/ws",
        "messagePostFormat": "array",
        "reportSelfMessage": false,
        "token": "",
        "enableForcePushEvent": true,
        "debug": false,
        "heartInterval": 30000
      }
    ]
  },
  "musicSignUrl": "",
  "enableLocalFile2Url": true,
  "parseMultMsg": true
}
CONF
    docker compose up -d --build
    echo ""
    echo "[✓] Services started!"
    echo "    NapCat WebUI: http://localhost:6099"
    echo "    NoneBot2:     http://localhost:6060"
    echo ""
    echo "    Scan QR code in NapCat WebUI to login QQ."
    echo "    Logs: docker compose logs -f"
    ;;

  stop)
    echo "[*] Stopping..."
    docker compose down
    ;;

  logs)
    docker compose logs -f
    ;;

  *)
    echo "[*] Starting conic-qqbot (local mode)..."
    if [ ! -d ".venv" ]; then
      echo "[*] Creating virtual environment..."
      python3 -m venv .venv
    fi
    source .venv/bin/activate
    if [ ! -f ".venv/.deps_installed" ]; then
      echo "[*] Installing dependencies..."
      pip install -q \
        nonebot2[fastapi] nonebot-adapter-onebot \
        cn2an httpx markdown pymdown-extensions \
        jinja2 aiofiles Pillow mcstatus playwright \
        apscheduler nonebot-plugin-apscheduler \
        "uvicorn[standard]"
      playwright install chromium --with-deps 2>/dev/null || playwright install chromium
      touch .venv/.deps_installed
      echo "[✓] Dependencies installed."
    fi
    python bot.py
    ;;
esac
