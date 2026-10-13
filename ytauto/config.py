"""Tüm ayarlar ortam değişkenlerinden okunur. GitHub'da 'Variables' veya 'Secrets' olarak tanımlanır."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = ROOT / "state" / "history.json"
MUSIC_DIR = ROOT / "assets" / "music"
OUTPUT_DIR = ROOT / "output"


def env(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    return value.strip() if value and value.strip() else default


# --- İçerik ---
# Not: Linux'ta LANGUAGE adlı bir sistem değişkeni zaten var, o yüzden CONTENT_LANG kullanıyoruz.
CONTENT_LANG = env("CONTENT_LANG", "tr")
TTS_VOICE = env("TTS_VOICE", "tr-TR-AhmetNeural")  # kadın sesi için: tr-TR-EmelNeural
TTS_RATE = env("TTS_RATE", "+0%")
THEME = env("CHANNEL_THEME", "motivasyon ve ilham veren kısa hikâyeler")
FONT_NAME = env("FONT_NAME", "DejaVu Sans")

# --- Yapay zeka (senaryo yazımı) ---
LLM_PROVIDER = env("LLM_PROVIDER", "gemini").lower()  # gemini (ücretsiz kota) | anthropic (ücretli)
GEMINI_MODEL = env("GEMINI_MODEL", "gemini-2.5-flash")
ANTHROPIC_MODEL = env("ANTHROPIC_MODEL", "claude-haiku-5-5")

# --- YouTube ---
PRIVACY_STATUS = env("PRIVACY_STATUS", "private")  # ilk testlerde private; hazır olunca public
CATEGORY_ID = env("CATEGORY_ID", "22")
SYNTHETIC_MEDIA = env("CONTAINS_SYNTHETIC_MEDIA", "false").lower() == "true"
# API günlük kotası varsayılan olarak ~6 yükleme. Kota artışı onaylanınca 8 yapın.
MAX_UPLOADS_PER_DAY = int(env("MAX_UPLOADS_PER_DAY", "6"))
# Günde 8 çalışma var (UTC saat//3 = 0..7). Bu dilimlerde normal video, diğerlerinde Shorts üretilir.
# 2 ve 6 = 06:00 ve 18:00 UTC = Türkiye saatiyle 09:00 ve 21:00.
LONG_SLOTS = [int(x) for x in env("LONG_SLOTS", "2,6").split(",") if x.strip()]

FORMATS = {
    "short": {
        "width": 1080,
        "height": 1920,
        "orientation": "portrait",
        "scenes": (6, 8),
        "words": (85, 130),
        "sub_words": 3,
        "font_size": 88,
        "margin_v": 520,
        "margin_h": 90,
    },
    "long": {
        "width": 1920,
        "height": 1080,
        "orientation": "landscape",
        "scenes": (14, 18),
        "words": (850, 1200),
        "sub_words": 8,
        "font_size": 54,
        "margin_v": 70,
        "margin_h": 160,
    },
}
