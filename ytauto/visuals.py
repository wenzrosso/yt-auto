"""Pexels'ten (ücretsiz, atıfsız kullanılabilen) stok video indirir."""
import os
import random
from pathlib import Path
from typing import Optional

import requests

PEXELS_URL = "https://api.pexels.com/videos/search"
FALLBACK_QUERIES = ["nature landscape", "sunrise sky", "city lights night", "ocean waves", "forest path"]


def _pick_file(video: dict, fmt: dict) -> Optional[dict]:
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


def _download(url: str, out: Path, max_mb: int = 60) -> bool:
    try:
        with requests.get(url, stream=True, timeout=60) as r:
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


def fetch_clip(keywords: str, fmt: dict, work: Path, used_ids: set, index: int) -> Optional[Path]:
    """Sahne için bir stok video indirir. Bulunamazsa None döner (render düz renkli arka plan kullanır)."""
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        return None
    for query in [keywords] + random.sample(FALLBACK_QUERIES, 2):
        try:
            r = requests.get(
                PEXELS_URL,
                headers={"Authorization": key},
                params={
                    "query": query,
                    "orientation": fmt["orientation"],
                    "size": "medium",
                    "per_page": 12,
                },
                timeout=30,
            )
            r.raise_for_status()
            videos = [v for v in r.json().get("videos", []) if v.get("id") not in used_ids and v.get("duration", 0) >= 4]
        except (requests.RequestException, ValueError):
            continue
        random.shuffle(videos)
        for v in videos:
            f = _pick_file(v, fmt)
            if not f:
                continue
            out = work / f"stock_{index}.mp4"
            if _download(f["link"], out):
                used_ids.add(v["id"])
                return out
    print(f"[görüntü] sahne {index + 1} için video bulunamadı, düz arka plan kullanılacak")
    return None
