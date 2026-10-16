"""ffmpeg ile sahneleri birleştirir, altyazıyı gömer, isteğe bağlı fon müziği ekler.

İki görünüm vardır (config.FORMATS[...]["style"]):
  classic   - sade altyazı, eski görünüm (normal videolar)
  cinematic - koyu renk düzeltme, ortada büyük renk vurgulu yazı, filigran ve kanal adlı son kare (Shorts)
"""
import math
import random
import subprocess
from pathlib import Path
from typing import Optional

from . import config

FPS = 30
PAD_SECONDS = 0.30  # her sahne sonunda kısa bir nefes payı
OUTRO_SECONDS = 1.6  # kanal adı gösterilen son kare (yalnızca sinematik stil ve CHANNEL_NAME doluysa)
PALETTE = ["0x1b2a49", "0x2d1e4f", "0x14403c", "0x4a2a1a", "0x1f3b5c", "0x3a1f3d"]

# ASS renkleri &HBBGGRR& biçimindedir: yeşil, kırmızı, sarı (vurgu), beyaz ve altın (kanal adı)
EMPHASIS_COLORS = ["&H4DFF8C&", "&H5533FF&", "&H0AD6FF&"]
WHITE = "&HFFFFFF&"
GOLD = "&H0AD6FF&"

# Koyu, hafif soğuk tonlu, kontrastlı "sinematik" görünüm
GRADE = "eq=brightness=-0.09:contrast=1.14:saturation=0.72,colorbalance=bs=0.07:bm=0.03,vignette=angle=PI/4"


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


def _make_clip(src: Optional[Path], seconds: float, fmt: dict, out: Path, idx: int, dim: bool = False) -> None:
    w, h = fmt["width"], fmt["height"]
    cinematic = fmt.get("style") == "cinematic"
    enc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", "-an", str(out)]
    if src:
        vf = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={FPS},setsar=1"
        if cinematic:
            vf += "," + GRADE
            if dim:
                vf += ",eq=brightness=-0.18"
        vf += ",format=yuv420p"
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-i", str(src), "-t", f"{seconds:.4f}", "-vf", vf] + enc
    else:
        color = PALETTE[idx % len(PALETTE)]
        vf = "vignette," + ("eq=brightness=-0.15," if dim else "") + "format=yuv420p"
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c={color}:s={w}x{h}:r={FPS}",
            "-t", f"{seconds:.4f}", "-vf", vf,
        ] + enc
    run(cmd)


def _cs_time(t: float) -> str:
    cs = int(round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def _font_name() -> str:
    """İstenen yazı tipi kuruluysa onu, değilse fontconfig'in seçtiği yedeği kullanır."""
    want = config.FONT_NAME
    try:
        out = subprocess.run(
            ["fc-match", want, "-f", "%{family}"], capture_output=True, text=True, timeout=10
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return want  # fc-match yok: yazı tipini doğrudan libass çözümlesin, bulamazsa kendi yedeğini kullanır
    if not out:
        return "DejaVu Sans"
    if want.lower() in out.lower():
        return want
    return out.split(",")[0].strip() or "DejaVu Sans"


def _emph_words(text: str) -> list:
    """'Kimse *inanmıyor*.' -> [('Kimse', False), ('inanmıyor.', True)]. Yıldız içindeki kelimeler vurgulanır."""
    words, emph = [], False
    for tok in text.replace("{", "").replace("}", "").replace("\\", "").split():
        starts = tok.lstrip("\"'“‘(«").startswith("*")
        ends = tok.rstrip(".,!?;:…\"'”’)»").endswith("*")
        word = tok.replace("*", "")
        if starts:
            emph = True
        if word:
            words.append((word, emph))
        if ends:
            emph = False
    return words


def _chunk_tokens(tokens: list, max_words: int) -> list:
    chunks, cur = [], []
    for item in tokens:
        cur.append(item)
        last = item[0][-1]
        strong = last in ".!?…"
        weak = last in ",;:"
        if len(cur) >= max_words or strong or (weak and len(cur) >= max(2, max_words // 2 + 1)):
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    return chunks


def _chunk_words(text: str, max_words: int) -> list:
    return [" ".join(w for w, _ in c) for c in _chunk_tokens(_emph_words(text), max_words)]


def _highlight(chunk: list, color: str) -> str:
    """Bir altyazı parçasını ASS metnine çevirir; vurgulu kelimeler renklenir."""
    if not any(e for _, e in chunk):
        # Model vurgu işareti koymadıysa en uzun kelimeyi vurgula
        clean = [w.strip(".,!?;:…\"'") for w, _ in chunk]
        i = max(range(len(chunk)), key=lambda k: len(clean[k]))
        if len(clean[i]) >= 5:
            chunk = [(w, k == i) for k, (w, _) in enumerate(chunk)]
    parts = [f"{{\\1c{color}}}{w}{{\\1c{WHITE}}}" if e else w for w, e in chunk]
    return " ".join(parts)


def _ass_header(fmt: dict, styles: list) -> str:
    return (
        "[Script Info]\nScriptType: v4.00+\n"
        f"PlayResX: {fmt['width']}\nPlayResY: {fmt['height']}\nWrapStyle: 0\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
        "MarginR, MarginV, Encoding\n"
        + "\n".join(styles)
        + "\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )


def _build_ass_classic(fmt: dict, timing: list, path: Path) -> None:
    style = (
        f"Style: Default,{_font_name()},{fmt['font_size']},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,"
        f"-1,0,0,0,100,100,0,0,1,{max(3, fmt['font_size'] // 16)},2,2,{fmt['margin_h']},{fmt['margin_h']},"
        f"{fmt['margin_v']},1"
    )
    lines = []
    for offset, speech, narration in timing:
        chunks = _chunk_words(narration, fmt["sub_words"])
        weights = [len(c) + 1 for c in chunks]
        total = sum(weights)
        t = offset
        for chunk, wgt in zip(chunks, weights):
            end = t + speech * wgt / total
            lines.append(f"Dialogue: 0,{_cs_time(t)},{_cs_time(end)},Default,,0,0,0,,{chunk}")
            t = end
    path.write_text(_ass_header(fmt, [style]) + "\n".join(lines) + "\n", encoding="utf-8")


def _build_ass_cinematic(fmt: dict, timing: list, path: Path, main_end: float, outro: float) -> None:
    w, h = fmt["width"], fmt["height"]
    font = _font_name()
    name = config.CHANNEL_NAME.replace("{", "").replace("}", "").replace("\\", "").strip()
    side = int(w * 0.10)
    styles = [
        # Ortada büyük, kalın, gölgeli yazı
        f"Style: Cap,{font},{fmt['font_size']},&H00FFFFFF,&H000000FF,&H00000000,&H90000000,"
        f"-1,0,0,0,100,100,0,0,1,4,3,5,{side},{side},0,1",
        # Filigran (yarı saydam) ve son karedeki kanal adı
        f"Style: Mark,{font},{max(36, int(w * 0.05))},&H000AD6FF,&H000000FF,&H00000000,&H00000000,"
        "-1,0,0,0,100,100,2,0,1,0,0,5,0,0,0,1",
        f"Style: Outro,{font},{int(w * 0.085)},&H000AD6FF,&H000000FF,&H00000000,&H90000000,"
        f"-1,0,0,0,100,100,2,0,1,3,3,5,{side},{side},0,1",
    ]
    cy = int(h * 0.47)
    lines, n = [], 0
    for offset, speech, narration in timing:
        chunks = _chunk_tokens(_emph_words(narration), fmt["sub_words"])
        weights = [sum(len(x[0]) + 1 for x in c) for c in chunks]
        total = sum(weights)
        t = offset
        for chunk, wgt in zip(chunks, weights):
            end = t + speech * wgt / total
            color = EMPHASIS_COLORS[n % len(EMPHASIS_COLORS)]
            n += 1
            tags = f"{{\\an5\\pos({w // 2},{cy})\\fscx90\\fscy90\\t(0,140,\\fscx100\\fscy100)\\fad(80,40)}}"
            lines.append(f"Dialogue: 0,{_cs_time(t)},{_cs_time(end)},Cap,,0,0,0,,{tags}{_highlight(chunk, color)}")
            t = end
    if name:
        tags = f"{{\\an5\\pos({w // 2},{int(h * 0.77)})\\1a&H78&}}"
        lines.append(f"Dialogue: 1,{_cs_time(0)},{_cs_time(main_end)},Mark,,0,0,0,,{tags}{name}")
        if outro > 0:
            tags = f"{{\\an5\\pos({w // 2},{cy})\\fscx92\\fscy92\\t(0,500,\\fscx100\\fscy100)\\fad(250,0)}}"
            lines.append(
                f"Dialogue: 1,{_cs_time(main_end)},{_cs_time(main_end + outro)},Outro,,0,0,0,,{tags}{name}"
            )
    path.write_text(_ass_header(fmt, styles) + "\n".join(lines) + "\n", encoding="utf-8")


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
    main_end = offset

    # Sinematik stilde ve kanal adı verilmişse sona kanal adlı kısa bir kare ekle
    outro = 0.0
    if fmt.get("style") == "cinematic" and config.CHANNEL_NAME.strip():
        outro = OUTRO_SECONDS
        clip = work / "clip_outro.mp4"
        _make_clip(scenes[-1].get("video"), outro, fmt, clip, len(scenes), dim=True)
        wav = work / "voice_outro.wav"
        run([
            "ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
            "-t", f"{outro:.4f}", "-ar", "44100", "-ac", "1", str(wav),
        ])
        clip_names.append(clip.name)
        wav_names.append(wav.name)
        offset += outro
    print(f"[render] {len(scenes)} sahne hazır, toplam {offset:.1f} sn")

    (work / "clips.txt").write_text("".join(f"file '{n}'\n" for n in clip_names), encoding="utf-8")
    (work / "wavs.txt").write_text("".join(f"file '{n}'\n" for n in wav_names), encoding="utf-8")
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "clips.txt", "-c", "copy", "video.mp4"], cwd=work)
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "wavs.txt", "-c", "copy", "voice.wav"], cwd=work)

    audio = "voice.wav"
    music = _pick_music()
    if music:
        print(f"[render] fon müziği: {music.name}")
        fade = f"afade=t=out:st={max(0.0, offset - 1.5):.2f}:d=1.5"
        run([
            "ffmpeg", "-y", "-loglevel", "error", "-i", "voice.wav", "-stream_loop", "-1", "-i", str(music),
            "-filter_complex",
            f"[1:a]volume={config.MUSIC_VOLUME}[m];"
            f"[0:a][m]amix=inputs=2:duration=first:dropout_transition=0,volume=2,{fade},alimiter=limit=0.95[a]",
            "-map", "[a]", "-ar", "44100", "mixed.wav",
        ], cwd=work)
        audio = "mixed.wav"

    if fmt.get("style") == "cinematic":
        _build_ass_cinematic(fmt, timing, work / "subs.ass", main_end, outro)
    else:
        _build_ass_classic(fmt, timing, work / "subs.ass")
    base = ["ffmpeg", "-y", "-loglevel", "error", "-i", "video.mp4", "-i", audio, "-map", "0:v", "-map", "1:a"]
    tail = ["-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "-shortest", "final.mp4"]
    try:
        run(base + ["-vf", "subtitles=subs.ass", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p"] + tail, cwd=work)
    except RuntimeError as e:
        print(f"[render] UYARI: altyazı gömülemedi, altyazısız devam ediliyor.\n{e}")
        run(base + ["-c:v", "copy"] + tail, cwd=work)
    return work / "final.mp4"
