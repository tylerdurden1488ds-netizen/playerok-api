"""Bothost bootstrap for exfador/playerok-api.

Use this file as the Bothost entrypoint instead of main.py.
It makes conf/ and db/ persistent under /app/data and supplies the
project's first-run interactive wizard from Bothost environment variables.
"""
from __future__ import annotations

import builtins
import getpass
import os
import runpy
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_ROOT = Path(os.getenv("BOTHOST_DATA_DIR", "/app/data"))


def _env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value is not None and value != "":
            return value
    return default


def _persist_dir(name: str) -> None:
    """Keep mutable project data in Bothost's persistent /app/data volume."""
    src = ROOT / name
    dst = DATA_ROOT / name
    DATA_ROOT.mkdir(parents=True, exist_ok=True)

    # Already linked correctly.
    if src.is_symlink() and src.resolve() == dst.resolve():
        dst.mkdir(parents=True, exist_ok=True)
        return

    dst.mkdir(parents=True, exist_ok=True)

    # Preserve anything that may already have been created locally.
    if src.exists() and not src.is_symlink():
        if src.is_dir():
            for child in src.iterdir():
                target = dst / child.name
                if target.exists():
                    continue
                if child.is_dir():
                    shutil.copytree(child, target)
                else:
                    shutil.copy2(child, target)
            shutil.rmtree(src)
        else:
            src.unlink()
    elif src.is_symlink():
        src.unlink()

    src.symlink_to(dst, target_is_directory=True)


for directory in ("conf", "db"):
    try:
        _persist_dir(directory)
    except Exception as exc:
        print(f"[Bothost] Warning: could not persist {directory}: {exc}", flush=True)


def _answer(prompt: str = "", *args, **kwargs) -> str:
    """Answer the upstream first-run wizard from environment variables."""
    p = (prompt or "").strip().lower()

    bot_token = _env("BOT_TOKEN", "TELEGRAM_BOT_TOKEN", "API_TOKEN", "TOKEN")
    admin_password = _env("ADMIN_PASSWORD", "PANEL_PASSWORD")
    playerok_token = _env("PLAYEROK_TOKEN", "PLAYEROK_JWT")
    playerok_cookies = _env("PLAYEROK_COOKIES")
    user_agent = _env("PLAYEROK_USER_AGENT", "USER_AGENT")
    playerok_proxy = _env("PLAYEROK_PROXY")
    telegram_proxy = _env("TELEGRAM_PROXY")

    # Telegram bot token.
    if ("telegram" in p or "бот" in p or "bot" in p) and "token" in p:
        value = bot_token
    # Admin/panel password.
    elif "парол" in p or "password" in p:
        value = admin_password
    # Browser User-Agent.
    elif "user-agent" in p or "user agent" in p or "юзер-агент" in p or "юзерагент" in p:
        value = user_agent
    # Playerok auth. Prefer JWT token, then cookie header/string.
    elif "playerok" in p and ("jwt" in p or "token" in p or "токен" in p):
        value = playerok_token or playerok_cookies
    elif "cookie" in p or "кук" in p:
        value = playerok_cookies or playerok_token
    # Proxy yes/no prompts.
    elif "proxy" in p or "прокси" in p:
        is_yes_no = any(x in p for x in ("y/n", "yes/no", "да/нет", "[y", "(y"))
        chosen = telegram_proxy if ("telegram" in p or "bot" in p or "бот" in p) else playerok_proxy
        if is_yes_no:
            value = "y" if chosen else "n"
        else:
            value = chosen
    else:
        # Optional/default wizard question: accept its default.
        value = ""

    # Do not echo secrets. Show only which question was answered.
    label = prompt.strip().replace("\n", " ")[:100]
    print(f"[Bothost] auto-answer: {label}", flush=True)
    return value


def _validate_env() -> None:
    config = ROOT / "conf" / "config.json"
    if config.exists():
        return

    missing = []
    if not _env("BOT_TOKEN", "TELEGRAM_BOT_TOKEN", "API_TOKEN", "TOKEN"):
        missing.append("BOT_TOKEN")
    if not _env("ADMIN_PASSWORD", "PANEL_PASSWORD"):
        missing.append("ADMIN_PASSWORD")
    if not _env("PLAYEROK_TOKEN", "PLAYEROK_JWT", "PLAYEROK_COOKIES"):
        missing.append("PLAYEROK_TOKEN")
    if not _env("PLAYEROK_USER_AGENT", "USER_AGENT"):
        missing.append("PLAYEROK_USER_AGENT")

    if missing:
        raise SystemExit(
            "[Bothost] Missing environment variables for first setup: "
            + ", ".join(missing)
        )


_validate_env()

# Feed the project's first-run setup wizard without an interactive TTY.
builtins.input = _answer
getpass.getpass = _answer

os.chdir(ROOT)
runpy.run_path(str(ROOT / "main.py"), run_name="__main__")
