"""Settings + watchlist loading for Deal Hunter."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # dotenv is optional; plain env vars work too
    load_dotenv = None

ROOT = Path(__file__).resolve().parent


@dataclass
class Settings:
    check_interval_minutes: int = 30
    cooldown_hours: float = 12.0        # min gap between two alerts for the same product
    default_drop_pct: float = 5.0       # alert when price falls this % vs last check
    git_sync: bool = False              # PC daemon: pull/push state so cloud + PC never double-alert
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_pass: str = ""
    email_to: str = ""
    telegram_token: str = ""
    telegram_chat_id: str = ""
    state_file: Path = field(default_factory=lambda: ROOT / "state.json")

    @property
    def email_enabled(self) -> bool:
        return bool(self.smtp_user and self.smtp_pass and self.email_to)


def get_settings() -> Settings:
    if load_dotenv:
        load_dotenv(ROOT / ".env")
    s = Settings()
    s.check_interval_minutes = int(os.getenv("CHECK_INTERVAL_MINUTES", s.check_interval_minutes))
    s.cooldown_hours = float(os.getenv("COOLDOWN_HOURS", s.cooldown_hours))
    s.default_drop_pct = float(os.getenv("DEFAULT_DROP_PCT", s.default_drop_pct))
    s.git_sync = os.getenv("GIT_SYNC", "0").strip().lower() in ("1", "true", "yes")
    s.smtp_host = os.getenv("SMTP_HOST", s.smtp_host)
    s.smtp_port = int(os.getenv("SMTP_PORT", s.smtp_port))
    s.smtp_user = os.getenv("SMTP_USER", "").strip()
    s.smtp_pass = os.getenv("SMTP_PASS", "").strip()
    s.email_to = os.getenv("EMAIL_TO", "").strip()
    s.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    s.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if os.getenv("STATE_FILE"):
        s.state_file = Path(os.getenv("STATE_FILE"))
    return s


def get_watchlist() -> dict:
    """Load watchlist.json: {my_cards: [...], products: [...]}"""
    path = ROOT / "watchlist.json"
    if not path.exists():
        return {"my_cards": [], "products": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("my_cards", [])
    data.setdefault("products", [])
    return data
