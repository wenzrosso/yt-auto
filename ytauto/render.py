"""ffmpeg ile sahneleri birleştirir, altyazıyı gömer, isteğe bağlı fon müziği ekler."""
import math
import random
import subprocess
from pathlib import Path
from typing import Optional

from . import config

FPS = 30
PAD_SECONDS = 0.30  # her sahne sonunda kısa bir nefes payı
PALETTE = ["0x1b2a49", "0x2d1e4f", "0x14403c", "0x4a2a1a", "0x1f3b5c", "0x3a1f3d"]


def run(cmd: list, cwd: Optional[Path] = None) -> None:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg hatası ({' '.join(cmd[:4])} ...):\n{proc.stderr[-1500:]}")


def duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(out)


def _make_clip(src: Optional[Path], seconds: float, fmt: dict, out: Path, idx: int) -> None:
    w, h = fmt["width"], fmt["height"]
    enc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", "-an", str(out)]
    if src:
        vf = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={FPS},setsar=1,format=yuv420p"
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-i", str(src), "-t", f"{seconds:.4f}", "-vf", vf] + enc
    else:
        color = PALETTE[idx % len(PALETTE)]
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c={color}:s={w}x{h}:r={FPS}",
            "-t", f"{seconds:.4f}", "-vf", "vignette,format=yuv420p",
        ] + enc
    run(cmd)


def _cs_time(t: float) -> str:
    cs = int(round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def _chunk_words(text: str, max_words: int) -> list:
    chunks, cur = [], []
    for w in text.split():
        cur.append(w)
        strong = w[-1] in ".!?…"
        weak = w[-1] in ",;:"
        if len(cur) >= max_words or strong or (weak and len(cur) >= max(2, max_words // 2 + 1)):
            chunks.append(" ".join(cur))
            cur = []
    if cur:
        chunks.append(" ".join(cur))
    return chunks


def _build_ass(fmt: dict, timing: list, path: Path) -> None:
    header = (
        "[Script Info]\nScriptType: v4.00+\n"
        f"PlayResX: {fmt['width']}\nPlayResY: {fmt['height']}\nWrapStyle: 0\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
        "MarginR, MarginV, Encoding\n"
        f"Style: Default,{config.FONT_NAME},{fmt['font_size']},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,"
        f"-1,0,0,0,100,100,0,0,1,{max(3, fmt['font_size'] // 16)},2,2,{fmt['margin_h']},{fmt['margin_h']},"
        f"{fmt['margin_v']},1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    lines = []
    for offset, speech, narration in timing:
        chunks = _chunk_words(narration.replace("{", "").replace("}", ""), fmt["sub_words"])
        weights = [len(c) + 1 for c in chunks]
        total = sum(weights)
        t = offset
        for chunk, wgt in zip(chunks, weights):
            end = t + speech * wgt / total
            lines.append(f"Dialogue: 0,{_cs_time(t)},{_cs_time(end)},Default,,0,0,0,,{chunk}")
            t = end
    path.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")


def _pick_music() -> Optional[Path]:
    tracks = [p for p in config.MUSIC_DIR.glob("*") if p.suffix.lower() in (".mp3", ".wav", ".m4a", ".ogg")]
    return random.choice(tracks) if tracks else None


def render_video(work: Path, fmt: dict, scenes: list) -> Path:
    """scenes: [{'audio': Path, 'video': Path|None, 'narration': str}, ...] -> final.mp4"""
    work = Path(work)
    clip_names, wav_names, timing = [], [], []
    offset = 0.0
    for i, sc in enumerate(scenes):
        speech = duration(sc["audio"])
        # Süreyi kare sınırına yuvarla: görüntü ve ses sahne sahne birebir aynı uzunlukta kalır, kayma olmaz.
        length = math.ceil((speech + PAD_SECONDS) * FPS) / FPS
        wav = work / f"voice_{i}.wav"
        run([
            "ffmpeg", "-y", "-loglevel", "error", "-i", str(sc["audio"]),
            "-af", f"apad=whole_dur={length:.4f}", "-t", f"{length:.4f}", "-ar", "44100", "-ac", "1", str(wav),
        ])
        clip = work / f"clip_{i}.mp4"
        _make_clip(sc.get("video"), length, fmt, clip, i)
        wav_names.append(wav.name)
        clip_names.append(clip.name)
        timing.append((offset, speech, sc["narration"]))
        offset += length
    print(f"[render] {len(scenes)} sahne hazır, toplam {offset:.1f} sn")

    (work / "clips.txt").write_text("".join(f"file '{n}'\n" for n in clip_names), encoding="utf-8")
    (work / "wavs.txt").write_text("".join(f"file '{n}'\n" for n in wav_names), encoding="utf-8")
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "clips.txt", "-c", "copy", "video.mp4"], cwd=work)
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "wavs.txt", "-c", "copy", "voice.wav"], cwd=work)

    audio = "voice.wav"
    music = _pick_music()
    if music:
        print(f"[render] fon müziği: {music.name}")
        run([
            "ffmpeg", "-y", "-loglevel", "error", "-i", "voice.wav", "-stream_loop", "-1", "-i", str(music),
            "-filter_complex",
            "[1:a]volume=0.10[m];[0:a][m]amix=inputs=2:duration=first:dropout_transition=0,volume=2,alimiter=limit=0.95[a]",
            "-map", "[a]", "-ar", "44100", "mixed.wav",
        ], cwd=work)
        audio = "mixed.wav"

    _build_ass(fmt, timing, work / "subs.ass")
    base = ["ffmpeg", "-y", "-loglevel", "error", "-i", "video.mp4", "-i", audio, "-map", "0:v", "-map", "1:a"]
    tail = ["-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "-shortest", "final.mp4"]
    try:
        run(base + ["-vf", "subtitles=subs.ass", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p"] + tail, cwd=work)
    except RuntimeError as e:
        print(f"[render] UYARI: altyazı gömülemedi, altyazısız devam ediliyor.\n{e}")
        run(base + ["-c:v", "copy"] + tail, cwd=work)
    return work / "final.mp4"
