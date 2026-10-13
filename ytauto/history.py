"""Yüklenen videoların kaydı: tekrarı önlemek ve günlük kotayı saymak için."""
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from . import config

# YouTube API kotası Pasifik saatiyle gece yarısı sıfırlanır.
PACIFIC = ZoneInfo("America/Los_Angeles")


def load() -> list:
    try:
        return json.loads(config.STATE_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save(items: list) -> None:
    config.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    config.STATE_FILE.write_text(
        json.dumps(items[-500:], ensure_ascii=False, indent=1), encoding="utf-8"
    )


def uploads_today(items: list) -> int:
    today = datetime.now(PACIFIC).date()
    count = 0
    for it in items:
        try:
            ts = datetime.fromisoformat(it["ts"]).astimezone(PACIFIC).date()
        except (KeyError, ValueError):
            continue
        if ts == today:
            count += 1
    return count


def recent_titles(items: list, n: int = 25) -> list:
    return [it.get("title", "") for it in items[-n:] if it.get("title")]


def add(items: list, kind: str, title: str, video_id: str) -> None:
    items.append(
        {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "kind": kind,
            "title": title,
            "video_id": video_id,
        }
    )
