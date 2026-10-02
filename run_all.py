"""Unified 24/7 Production Runner.

Runs both:
1. FastAPI WebApp & API server on $PORT (0.0.0.0)
2. Telegram Bot (@dabi_plays_bot) polling concurrently in background
3. Self-ping keep-alive to keep Cloud hosting (Render/Railway) awake 24/7
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys

import httpx
import uvicorn
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("production-runner")


async def keep_alive_loop(app_url: str) -> None:
    """Send periodic health pings to prevent cloud host from sleeping."""
    if not app_url or "localhost" in app_url or "127.0.0.1" in app_url:
        return

    health_url = app_url.rstrip("/") + "/health"
    log.info("⏰ 24/7 Keep-Alive faollashtirildi: %s (har 10 daqiqada)", health_url)
    
    # Wait 2 minutes after startup before first ping
    await asyncio.sleep(120)
    
    while True:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.get(health_url)
                if res.status_code == 200:
                    log.info("💓 24/7 Keep-Alive muvaffaqiyatli: %s (Status 200)", health_url)
                else:
                    log.warning("⚠️ Keep-Alive status: %s", res.status_code)
        except Exception as ex:
            log.warning("Keep-Alive pingda xatolik: %s", ex)

        # Ping every 10 minutes (600 seconds)
        await asyncio.sleep(600)


async def start_services() -> None:
    """Initialize DB and run FastAPI + Telegram Bot concurrently."""
    try:
        from database import init_db
    except ImportError:
        from api.database import init_db

    init_db()

    # 1. Start Telegram Bot in background task
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if bot_token:
        try:
            from bot.bot import main as start_bot
            log.info("🤖 Telegram bot polling ishga tushirilmoqda...")
            asyncio.create_task(start_bot())
        except Exception as e:
            log.error("Telegram botni ishga tushirishda xatolik: %s", e)
    else:
        log.warning("⚠️ BOT_TOKEN topilmadi, bot ishga tushmadi.")

    # 2. Start Keep-Alive task if public API_URL is configured
    public_url = os.getenv("API_URL", "") or os.getenv("RENDER_EXTERNAL_URL", "")
    if public_url:
        asyncio.create_task(keep_alive_loop(public_url))

    # 3. Start Uvicorn Server for WebApp and REST API
    port = int(os.getenv("PORT", "8000"))
    host = "0.0.0.0"
    log.info("🌐 FastAPI WebApp server %s:%d portida ishga tushmoqda...", host, port)

    config = uvicorn.Config(
        "api.main:app",
        host=host,
        port=port,
        log_level="info",
        access_log=False,
    )
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    try:
        asyncio.run(start_services())
    except (KeyboardInterrupt, SystemExit):
        log.info("Server to'xtatildi.")
