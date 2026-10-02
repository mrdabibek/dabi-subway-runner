"""Write a public HTTPS tunnel URL into .env for the Telegram WebApp."""

from __future__ import annotations

import re
import sys
import os
from pathlib import Path
from urllib.parse import urlparse


ENV_PATH = Path(__file__).resolve().parent / ".env"


def update_urls(base: str) -> None:
    base = base.strip().rstrip("/")
    parsed = urlparse(base)
    if parsed.scheme != "https" or not parsed.hostname or parsed.path or parsed.query or parsed.fragment:
        raise ValueError("HTTPS tunnel asosiy manzilini kiriting (masalan, https://xxx.trycloudflare.com)")
    text = ENV_PATH.read_text(encoding="utf-8")
    for key, value in (("WEBAPP_URL", base + "/webapp/"), ("API_URL", base)):
        pattern = rf"(?m)^{key}=.*$"
        if re.search(pattern, text):
            text = re.sub(pattern, lambda _: f"{key}={value}", text)
        else:
            text += f"\n{key}={value}\n"
    temporary = ENV_PATH.with_name(".env.tmp")
    try:
        temporary.write_text(text, encoding="utf-8")
        os.replace(temporary, ENV_PATH)
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        update_urls(sys.argv[1] if len(sys.argv) > 1 else "")
    except (OSError, ValueError) as exc:
        print("[ERROR]", exc)
        raise SystemExit(1)
    print("[OK] WebApp va API manzillari yangilandi.")
