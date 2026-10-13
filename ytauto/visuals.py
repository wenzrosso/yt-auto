"""Ücretsiz stok video kaynakları: Pexels (anahtar varsa önce o) ve Pixabay."""
import os
import random
from pathlib import Path
from typing import Optional

import requests

PEXELS_URL = "https://api.pexels.com/videos/search"
PIXABAY_URL = "https://pixabay.com/api/videos/"
FALLBACK_QUERIES = ["nature landscape", "sunrise sky", "city lights night", "ocean waves", "forest path"]
MAX_PIXABAY_BYTES = 70 * 1024 * 1024

# Hangi kaynaklardan görüntü kullanıldı (video açıklamasına yazılır)
SOURCES_USED: set = set()


def has_any_key() -> bool:
    return bool(os.environ.get("PEXELS_API_KEY") or os.environ.get("PIXABAY_API_KEY"))


def _download(url: str, out: Path, max_mb: int = 60) -> bool:
    try:
        with requests.get(url, stream=True, timeout=90) as r:
            r.raise_for_status()
            size = 0
            with open(out, "wb") as fh:
                for chunk in r.iter_content(1024 * 256):
                    size += len(chunk)
                    if size > max_mb * 1024 * 1024:
                        return False
                    fh.write(chunk)
        return out.exists() and out.stat().st_size > 10_000
    except requests.RequestException:
        return False


# ---------------------------------------------------------------- Pexels
def _pick_pexels_file(video: dict, fmt: dict) -> Optional[dict]:
    portrait = fmt["orientation"] == "portrait"
    files = [
        f
        for f in video.get("video_files", [])
        if f.get("file_type") == "video/mp4"
        and f.get("width")
        and f.get("height")
        and ((f["height"] > f["width"]) if portrait else (f["width"] >= f["height"]))
    ]
    if not files:
        return None
    enough = [f for f in files if f["width"] >= fmt["width"] * 0.9 and f["height"] >= fmt["height"] * 0.9]
    if enough:  # hedefi karşılayan en küçük dosya: hızlı indirme, yeterli kalite
        return min(enough, key=lambda f: f["width"] * f["height"])
    return max(files, key=lambda f: f["width"] * f["height"])


def _pexels(keywords: str, fmt: dict, work: Path, used_ids: set, index: int) -> Optional[Path]:
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        return None
    for query in [keywords] + random.sample(FALLBACK_QUERIES, 2):
        try:
            r = requests.get(
                PEXELS_URL,
                headers={"Authorization": key},
                params={"query": query, "orientation": fmt["orientation"], "size": "medium", "per_page": 12},
                timeout=30,
            )
            r.raise_for_status()
            videos = [
                v
                for v in r.json().get("videos", [])
                if f"pexels:{v.get('id')}" not in used_ids and v.get("duration", 0) >= 4
            ]
        except (requests.RequestException, ValueError):
            continue
        random.shuffle(videos)
        for v in videos:
            f = _pick_pexels_file(v, fmt)
            if not f:
                continue
            out = work / f"stock_{index}.mp4"
            if _download(f["link"], out):
                used_ids.add(f"pexels:{v['id']}")
                SOURCES_USED.add("Pexels")
                return out
    return None


# --------------------------------------------------------------- Pixabay
def _is_portrait(hit: dict) -> bool:
    return any(
        (r or {}).get("height", 0) > (r or {}).get("width", 0) for r in (hit.get("videos") or {}).values()
    )


def _pick_pixabay_rendition(hit: dict, fmt: dict) -> Optional[dict]:
    """Hedef çözünürlüğe büyütme yapmadan yetecek en küçük dosyayı seç.

    Dikey (Shorts) için yatay bir kaynak ortadan kırpıldığından 4K ('large') sürüm gerekir; aksi halde
    1080p kaynak büyütülür ve bulanık çıkar.
    """
    tw, th = fmt["width"], fmt["height"]
    cands = []
    for name in ("large", "medium", "small", "tiny"):
        r = (hit.get("videos") or {}).get(name) or {}
        if not (r.get("url") and r.get("width") and r.get("height")):
            continue
        if r.get("size") and r["size"] > MAX_PIXABAY_BYTES:
            continue
        scale = max(tw / r["width"], th / r["height"])  # >1 ise büyütme gerekir
        cands.append((scale, r))
    if not cands:
        return None
    sharp = [c for c in cands if c[0] <= 1.0001]
    if sharp:
        return min(sharp, key=lambda c: c[1].get("size") or 0)[1]
    return min(cands, key=lambda c: c[0])[1]


def _pixabay(keywords: str, fmt: dict, work: Path, used_ids: set, index: int) -> Optional[Path]:
    key = os.environ.get("PIXABAY_API_KEY")
    if not key:
        return None
    portrait = fmt["orientation"] == "portrait"
    for query in [keywords] + random.sample(FALLBACK_QUERIES, 2):
        try:
            r = requests.get(
                PIXABAY_URL,
                params={"key": key, "q": query[:100], "per_page": 30, "safesearch": "true", "video_type": "film"},
                timeout=30,
            )
            r.raise_for_status()
            hits = [
                h
                for h in r.json().get("hits", [])
                if f"pixabay:{h.get('id')}" not in used_ids and h.get("duration", 0) >= 4
            ]
        except (requests.RequestException, ValueError):
            continue
        random.shuffle(hits)
        if portrait:  # dikey kaynaklar varsa onları öne al (sıralama kararlı)
            hits.sort(key=lambda h: not _is_portrait(h))
        for h in hits:
            rend = _pick_pixabay_rendition(h, fmt)
            if not rend:
                continue
            out = work / f"stock_{index}.mp4"
            if _download(rend["url"], out, max_mb=80):
                used_ids.add(f"pixabay:{h['id']}")
                SOURCES_USED.add("Pixabay")
                return out
    return None


# ------------------------------------------------------------------ Ortak
def fetch_clip(keywords: str, fmt: dict, work: Path, used_ids: set, index: int) -> Optional[Path]:
    """Sahne için stok video indirir. Hiçbir kaynakta bulunamazsa None döner (düz renkli arka plan kullanılır)."""
    for provider in (_pexels, _pixabay):
        clip = provider(keywords, fmt, work, used_ids, index)
        if clip:
            return clip
    print(f"[görüntü] sahne {index + 1} için video bulunamadı, düz arka plan kullanılacak")
    return None
