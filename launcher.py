"""Run API, a Cloudflare quick tunnel, and bot with a fresh WebApp URL."""

from __future__ import annotations

import queue
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx

from update_webapp_url import update_urls


ROOT = Path(__file__).resolve().parent
LOCAL_HEALTH = "http://127.0.0.1:8000/health"
TUNNEL_URL = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com\b")
STOP_REQUEST = ROOT / ".stop_requested"


def wait_for_health(url: str, seconds: int, process: subprocess.Popen | None = None) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if process and process.poll() is not None:
            return False
        try:
            response = httpx.get(url, timeout=3, follow_redirects=True)
            if response.status_code == 200 and response.json().get("ok") is True:
                return True
        except (httpx.HTTPError, ValueError):
            pass
        time.sleep(1)
    return False


def read_tunnel_output(process: subprocess.Popen, lines: queue.Queue[str]) -> None:
    assert process.stderr is not None
    for line in process.stderr:
        print("[TUNNEL]", line.rstrip(), flush=True)
        lines.put(line)


def launch() -> int:
    STOP_REQUEST.unlink(missing_ok=True)
    cloudflared = shutil.which("cloudflared")
    if not cloudflared:
        print("[ERROR] cloudflared topilmadi. winget install Cloudflare.cloudflared")
        return 1

    processes: list[subprocess.Popen] = []
    try:
        api = subprocess.Popen(
            [sys.executable, "-c", "from api.main import app; import uvicorn; uvicorn.run(app, host='127.0.0.1', port=8000)"],
            cwd=ROOT,
        )
        processes.append(api)
        if not wait_for_health(LOCAL_HEALTH, 20, api):
            print("[ERROR] API ishga tushmadi. Yuqoridagi API xatosini tekshiring.")
            return 1

        base_url = None
        for attempt in range(1, 4):
            tunnel = subprocess.Popen(
                [cloudflared, "tunnel", "--url", "http://127.0.0.1:8000"],
                cwd=ROOT,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            processes.append(tunnel)
            lines: queue.Queue[str] = queue.Queue()
            threading.Thread(target=read_tunnel_output, args=(tunnel, lines), daemon=True).start()

            deadline = time.monotonic() + 60
            while time.monotonic() < deadline and tunnel.poll() is None:
                try:
                    line = lines.get(timeout=1)
                except queue.Empty:
                    continue
                match = TUNNEL_URL.search(line)
                if match:
                    base_url = match.group()
                    break
            if base_url and wait_for_health(base_url + "/health", 90, tunnel):
                break
            print(f"[WARN] Tunnel ochilmadi ({attempt}/3).", flush=True)
            base_url = None
            if tunnel.poll() is None:
                tunnel.terminate()
                tunnel.wait(timeout=5)
        if not base_url:
            print("[ERROR] HTTPS tunnel ishlamadi. Cloudflared xabarlarini tekshiring.")
            return 1

        update_urls(base_url)
        print("[OK] Telegram WebApp:", base_url + "/webapp/", flush=True)
        bot = subprocess.Popen([sys.executable, "-m", "bot.bot"], cwd=ROOT)
        processes.append(bot)
        print("[OK] API, tunnel va bot ishlayapti. To'xtatish: Ctrl+C", flush=True)

        last_health_check = time.monotonic()
        remote_failures = 0
        while True:
            if STOP_REQUEST.exists():
                print("[OK] To'xtatish so'rovi qabul qilindi.")
                return 0
            for name, process in (("API", api), ("TUNNEL", tunnel), ("BOT", bot)):
                if process.poll() is not None:
                    print(f"[ERROR] {name} to'xtadi (kod: {process.returncode}). Qayta ishga tushiring.")
                    return 1
            if time.monotonic() - last_health_check >= 30:
                if not wait_for_health(LOCAL_HEALTH, 5, api):
                    print("[ERROR] API javob bermayapti. run_all.bat ni qayta ishga tushiring.")
                    return 1
                if wait_for_health(base_url + "/health", 5, tunnel):
                    remote_failures = 0
                else:
                    remote_failures += 1
                    if remote_failures == 3:
                        print("[WARN] Tunnel 3 marta javob bermadi. Tarmoq tiklanmasa run_all.bat ni qayta ishga tushiring.", flush=True)
                last_health_check = time.monotonic()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[OK] Xizmatlar to'xtatilmoqda...")
        return 0
    finally:
        STOP_REQUEST.unlink(missing_ok=True)
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
        for process in reversed(processes):
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(launch())
