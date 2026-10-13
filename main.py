#!/usr/bin/env python3
"""Tek çalıştırmada bir video üretir ve YouTube'a yükler.

Örnekler:
    python main.py                      # saate göre Shorts ya da normal video seçer, üretir, yükler
    python main.py --kind short         # Shorts zorla
    python main.py --dry-run            # internet/API anahtarı olmadan deneme videosu üretir (output/ klasörüne)
    python main.py --no-upload          # gerçek içerik üretir ama yüklemez
"""
import argparse
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from ytauto import config, history, render, tts

SAMPLE_SCRIPT = {
    "title": "Deneme videosu: küçük adımlar",
    "description": "Bu bir deneme videosudur.",
    "tags": ["deneme", "motivasyon"],
    "scenes": [
        {"narration": "Bazen en büyük değişim, en küçük adımla başlar. Şimdi başlamak için doğru zaman.", "keywords": "sunrise mountain"},
        {"narration": "Her sabah yalnızca on dakika ayırsan, bir yılın sonunda kendine şaşıracaksın.", "keywords": "morning walk"},
        {"narration": "Önemli olan hız değil, bırakmadan devam etmek. İlerlemek için çok büyük olmak gerekmez.", "keywords": "road forest"},
        {"narration": "Bugün bir adım at ve yarın yeniden dene. Çünkü süreklilik, yeteneği her zaman yener.", "keywords": "ocean waves"},
    ],
}

FOOTER = "Bu videonun seslendirmesi yapay zekâ ile oluşturulmuştur. Görüntüler Pexels kaynaklıdır."


def choose_kind(arg: str) -> str:
    if arg != "auto":
        return arg
    slot = datetime.now(timezone.utc).hour // 3
    return "long" if slot in config.LONG_SLOTS else "short"


def build_description(script: dict, kind: str) -> str:
    parts = [script["description"], FOOTER]
    hashtags = ["#" + t.replace(" ", "") for t in script["tags"][:3]]
    if kind == "short":
        hashtags.insert(0, "#Shorts")
    if hashtags:
        parts.append(" ".join(hashtags))
    return "\n\n".join(p for p in parts if p)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=["auto", "short", "long"], default="auto")
    ap.add_argument("--dry-run", action="store_true", help="API kullanmadan deneme videosu üret")
    ap.add_argument("--no-upload", action="store_true", help="üret ama YouTube'a yükleme")
    args = ap.parse_args()

    local_only = args.dry_run or args.no_upload
    items = history.load()

    if not local_only:
        done = history.uploads_today(items)
        if done >= config.MAX_UPLOADS_PER_DAY:
            print(f"[atla] Bugün (Pasifik saatiyle) {done} video yüklendi; sınır {config.MAX_UPLOADS_PER_DAY}. Çıkılıyor.")
            return 0

    kind = choose_kind(args.kind)
    fmt = config.FORMATS[kind]
    if args.dry_run:
        script = SAMPLE_SCRIPT
    else:
        from ytauto import scriptgen  # ağ kütüphanelerini yalnızca gerektiğinde yükle

        script = scriptgen.generate(kind, history.recent_titles(items))
    print(f"[başlık] {script['title']}")

    work = Path(tempfile.mkdtemp(prefix="ytauto_"))
    try:
        scenes, used = [], set()
        for i, sc in enumerate(script["scenes"]):
            audio = work / (f"raw_{i}.wav" if args.dry_run else f"raw_{i}.mp3")
            if args.dry_run:
                tts.synth_fake(sc["narration"], audio)
                clip = None
            else:
                from ytauto import visuals

                tts.synth(sc["narration"], audio)
                clip = visuals.fetch_clip(sc["keywords"], fmt, work, used, i)
            scenes.append({"audio": audio, "video": clip, "narration": sc["narration"]})

        final = render.render_video(work, fmt, scenes)
        size_mb = final.stat().st_size / 1e6
        print(f"[render] bitti: {size_mb:.1f} MB, {render.duration(final):.1f} sn")

        if local_only:
            config.OUTPUT_DIR.mkdir(exist_ok=True)
            dest = config.OUTPUT_DIR / f"{'dry_run' if args.dry_run else 'video'}_{kind}.mp4"
            shutil.copy(final, dest)
            print(f"[çıktı] {dest}")
            return 0

        title = script["title"]
        if kind == "short" and "#shorts" not in title.lower():
            title += " #Shorts"
        from ytauto import uploader

        try:
            video_id = uploader.upload(
                final, title, build_description(script, kind), script["tags"], config.PRIVACY_STATUS
            )
        except uploader.QuotaExceeded as e:
            print(f"[kota] {e}")
            return 1
        history.add(items, kind, script["title"], video_id)
        history.save(items)
        print(f"[yüklendi] https://youtu.be/{video_id}  ({config.PRIVACY_STATUS})")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
