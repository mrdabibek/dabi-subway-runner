"""Automated 24/7 Self-Healing Watchdog for Subway Runner.

Runs continuously in background:
1. Starts Uvicorn server on port 8000 (auto-restarts on crash).
2. Starts Cloudflared tunnel (auto-restarts on network drop).
3. Automatically parses new trycloudflare.com URL whenever tunnel reconnects.
4. Automatically updates .env with the new active URL.
5. Automatically calls Telegram Bot API setChatMenuButton so the Play button always works!
6. Starts and monitors Telegram Bot (@dabi_plays_bot).
7. Keeps running 24/7 without needing manual commands.
"""
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "watchdog.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("watchdog")

CLOUDFLARED_EXE = r"C:\Program Files (x86)\cloudflared\cloudflared.exe"
ENV_PATH = BASE_DIR / ".env"


def read_env() -> dict[str, str]:
    data = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                data[k.strip()] = v.strip()
    return data


def update_env_urls(webapp_url: str, api_url: str) -> None:
    if not ENV_PATH.exists():
        return
    content = ENV_PATH.read_text(encoding="utf-8")
    if "WEBAPP_URL=" in content:
        content = re.sub(r"WEBAPP_URL=.*", f"WEBAPP_URL={webapp_url}", content)
    else:
        content += f"\nWEBAPP_URL={webapp_url}"

    if "API_URL=" in content:
        content = re.sub(r"API_URL=.*", f"API_URL={api_url}", content)
    else:
        content += f"\nAPI_URL={api_url}"

    ENV_PATH.write_text(content, encoding="utf-8")
    log.info("📝 .env yangilandi: %s", webapp_url)


def update_telegram_menu_button(token: str, webapp_url: str) -> bool:
    if not token or not webapp_url:
        return False
    url = f"https://api.telegram.org/bot{token}/setChatMenuButton"
    payload = json.dumps({
        "menu_button": {
            "type": "web_app",
            "text": "▶️ O'ynash",
            "web_app": {"url": webapp_url},
        }
    }).encode("utf-8")
    try:
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=10)
        res_data = json.loads(resp.read().decode("utf-8"))
        if res_data.get("ok"):
            log.info("✅ Telegram Chat Menu Button muvaffaqiyatli yangilandi!")
            return True
    except Exception as ex:
        log.warning("Telegram Menu Button yangilashda xato: %s", ex)
    return False


def is_uvicorn_alive() -> bool:
    try:
        req = urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=3)
        return req.status == 200
    except Exception:
        return False

import atexit
import threading

active_children: list[subprocess.Popen] = []

def cleanup_children() -> None:
    for p in active_children:
        if p and p.poll() is None:
            try:
                p.kill()
            except Exception:
                pass

atexit.register(cleanup_children)


def main_watchdog() -> None:
    log.info("🚀 24/7 Subway Runner Watchdog ishga tushdi...")
    env = read_env()
    bot_token = env.get("BOT_TOKEN", "")

    uvicorn_proc: subprocess.Popen | None = None
    cloudflared_proc: subprocess.Popen | None = None
    bot_proc: subprocess.Popen | None = None
    current_tunnel_url = ""
    lock = threading.Lock()

    def on_url_found(url: str) -> None:
        nonlocal current_tunnel_url, bot_proc
        with lock:
            if url and url != current_tunnel_url:
                current_tunnel_url = url
                webapp_url = f"{url}/webapp/"
                log.info("🌐 Yangi Cloudflare URL topildi: %s", url)
                update_env_urls(webapp_url, url)
                update_telegram_menu_button(bot_token, webapp_url)
                if bot_proc and bot_proc.poll() is None:
                    log.info("🔄 Bot yangi URL bilan qayta ishga tushirilmoqda...")
                    try:
                        bot_proc.kill()
                    except Exception:
                        pass
                    bot_proc = None

    def read_cf_output(proc: subprocess.Popen) -> None:
        cf_log_path = LOG_DIR / "cloudflared.log"
        try:
            with open(cf_log_path, "a", encoding="utf-8") as f:
                for line in iter(proc.stdout.readline, ""):
                    f.write(line)
                    f.flush()
                    m = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
                    if m:
                        on_url_found(m.group(0))
        except Exception as ex:
            log.warning("Cloudflare stream o'qishda xato: %s", ex)

    while True:
        try:
            # 1. Check Uvicorn
            if not is_uvicorn_alive():
                log.info("⚡ Uvicorn ishga tushirilmoqda (127.0.0.1:8000)...")
                if uvicorn_proc and uvicorn_proc.poll() is None:
                    try: uvicorn_proc.kill()
                    except Exception: pass
                uvicorn_proc = subprocess.Popen(
                    [sys.executable, "-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", "8000"],
                    cwd=str(BASE_DIR),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                active_children.append(uvicorn_proc)
                time.sleep(3)

            # 2. Check Cloudflared Tunnel
            if cloudflared_proc is None or cloudflared_proc.poll() is not None:
                log.info("⚡ Cloudflare Tunnel ishga tushirilmoqda...")
                cloudflared_proc = subprocess.Popen(
                    [CLOUDFLARED_EXE, "tunnel", "--edge-ip-version", "4", "--url", "http://127.0.0.1:8000"],
                    cwd=str(BASE_DIR),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                active_children.append(cloudflared_proc)
                t = threading.Thread(target=read_cf_output, args=(cloudflared_proc,), daemon=True)
                t.start()

                # Wait up to 15 seconds for URL detection
                start_w = time.time()
                while time.time() - start_w < 15 and not current_tunnel_url:
                    time.sleep(0.5)

            # 3. Check Telegram Bot
            if bot_proc is None or bot_proc.poll() is not None:
                log.info("🤖 Telegram Bot ishga tushirilmoqda (@%s)...", env.get("BOT_USERNAME", "dabi_plays_bot"))
                bot_proc = subprocess.Popen(
                    [sys.executable, "-m", "bot.bot"],
                    cwd=str(BASE_DIR),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                active_children.append(bot_proc)

        except Exception as ex:
            log.error("Watchdog monitoring xatosi: %s", ex)

        # Heartbeat check every 15 seconds
        time.sleep(15)


if __name__ == "__main__":
    main_watchdog()

