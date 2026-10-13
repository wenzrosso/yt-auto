"""Seslendirme: önce edge-tts (ücretsiz, doğal Türkçe sesler), olmazsa gTTS."""
import asyncio
import re
import subprocess
import time
from pathlib import Path

from . import config


def _clean(text: str) -> str:
    text = re.sub(r"[*_#`~<>]", "", text)
    return re.sub(r"\s+", " ", text).strip()


async def _edge(text: str, out: Path) -> None:
    import edge_tts

    comm = edge_tts.Communicate(text, config.TTS_VOICE, rate=config.TTS_RATE)
    await asyncio.wait_for(comm.save(str(out)), timeout=90)


def synth(text: str, out: Path, retries: int = 3) -> Path:
    text = _clean(text)
    last = None
    for i in range(retries):
        try:
            asyncio.run(_edge(text, out))
            if out.exists() and out.stat().st_size > 1000:
                return out
            last = "boş ses dosyası"
        except Exception as e:  # edge-tts çeşitli ağ hataları fırlatabilir
            last = e
        time.sleep(3 * (i + 1))
    print(f"[ses] edge-tts başarısız ({last}); gTTS deneniyor")
    from gtts import gTTS

    gTTS(text=text, lang=config.CONTENT_LANG).save(str(out))
    return out


def synth_fake(text: str, out: Path) -> Path:
    """--dry-run için: internet olmadan, kelime sayısına göre süresi hesaplanan sessiz bir ton üretir."""
    seconds = max(2.0, len(text.split()) * 0.42)
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", f"sine=frequency=180:duration={seconds:.2f}",
            "-af", "volume=0.05", str(out),
        ],
        check=True,
    )
    return out
