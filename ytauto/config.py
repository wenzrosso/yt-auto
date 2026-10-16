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
CONTENT_LANG = env("CONTENT_LANG", "en")  # en = İngilizce, tr = Türkçe
_DEFAULT_VOICE = {"en": "en-US-GuyNeural", "tr": "tr-TR-AhmetNeural"}  # kadın sesleri: en-US-AriaNeural, tr-TR-EmelNeural
_DEFAULT_THEME = {
    "en": "motivational and inspiring short stories",
    "tr": "motivasyon ve ilham veren kısa hikâyeler",
}
TTS_VOICE = env("TTS_VOICE", _DEFAULT_VOICE.get(CONTENT_LANG, _DEFAULT_VOICE["en"]))
TTS_RATE = env("TTS_RATE", "+0%")
THEME = env("CHANNEL_THEME", _DEFAULT_THEME.get(CONTENT_LANG, _DEFAULT_THEME["en"]))
FONT_NAME = env("FONT_NAME", "Poppins")  # kurulu değilse otomatik olarak DejaVu Sans'a düşer
# Shorts görünümü: cinematic = koyu, sinematik "disiplin/motivasyon" tarzı | classic = eski sade görünüm
SHORT_STYLE = env("SHORT_STYLE", "cinematic").lower()
# Filigran ve son karedeki kanal adı. Boş bırakılırsa gösterilmez.
CHANNEL_NAME = env("CHANNEL_NAME", "")
MUSIC_VOLUME = float(env("MUSIC_VOLUME", "0.14"))  # assets/music klasöründe müzik varsa ses seviyesi

# --- Yapay zeka (senaryo yazımı) ---
LLM_PROVIDER = env("LLM_PROVIDER", "gemini").lower()  # gemini (ücretsiz kota) | anthropic (ücretli)
GEMINI_MODEL = env("GEMINI_MODEL", "gemini-3.8-flash")
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

FORMATS["short"]["style"] = SHORT_STYLE if SHORT_STYLE in ("cinematic", "classic") else "cinematic"
FORMATS["long"]["style"] = "classic"

_EN = CONTENT_LANG.lower().startswith("en")
if FORMATS["short"]["style"] == "cinematic":
    # Kısa, vurucu, yaklaşık 20-30 saniyelik videolar; her sahne tek bir satır
    FORMATS["short"]["scenes"] = (7, 10)
    FORMATS["short"]["words"] = (50, 80) if _EN else (40, 65)
    FORMATS["short"]["sub_words"] = 10
    FORMATS["short"]["font_size"] = 84
elif _EN:
    FORMATS["short"]["words"] = (100, 140)  # yaklaşık 40-55 sn
if _EN:
    FORMATS["long"]["words"] = (900, 1250)  # yaklaşık 6-8 dk
