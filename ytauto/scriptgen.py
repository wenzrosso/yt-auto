"""Yapay zeka ile video senaryosu üretir: başlık, açıklama, etiketler ve sahne sahne anlatım."""
import random

from . import config, llm

ANGLES = [
    "sabah rutini ve disiplin",
    "başarısızlıktan ders çıkarmak",
    "pes etmemenin gücü",
    "erteleme alışkanlığından kurtulmak",
    "küçük adımların büyük sonuçları",
    "kendine güveni yeniden kazanmak",
    "zor zamanlarda sabır",
    "odaklanmak ve dikkat dağıtıcılardan uzak durmak",
    "korkularla yüzleşmek",
    "minnettarlık ve şükretmek",
    "başkalarıyla kıyaslamayı bırakmak",
    "yeni bir başlangıç yapmak",
    "iyi alışkanlık kurmanın sırrı",
    "hayır diyebilmek ve sınır koymak",
    "zamanı doğru kullanmak",
    "hata yapmaktan korkmamak",
    "sürekliliğin yeteneği yendiği an",
    "kendi hızında ilerlemek",
    "vazgeçmek ile yön değiştirmek arasındaki fark",
    "sıfırdan başlayıp ilerleyen birinin hikâyesi",
    "yorgunken bile devam etmek",
    "çevreni seçmenin önemi",
    "hedef koymak ve ona yürümek",
    "mükemmeliyetçiliği bırakmak",
]

SYSTEM = (
    "Sen deneyimli bir Türkçe YouTube senaristisin. Yalnızca geçerli JSON döndürürsün, "
    "başka hiçbir açıklama yazmazsın."
)

ANGLES_EN = [
    "building a morning routine and discipline",
    "learning from failure",
    "the power of not giving up",
    "overcoming procrastination",
    "how small steps create big results",
    "rebuilding your self-confidence",
    "patience in hard times",
    "focus and avoiding distractions",
    "facing your fears",
    "gratitude",
    "why you should stop comparing yourself to others",
    "making a fresh start",
    "the secret to building good habits",
    "learning to say no and set boundaries",
    "using your time wisely",
    "not being afraid of mistakes",
    "when consistency beats talent",
    "moving at your own pace",
    "the difference between quitting and changing direction",
    "the story of someone who started from zero",
    "keeping going when you are tired",
    "choosing the people around you",
    "setting a goal and walking toward it",
    "letting go of perfectionism",
]

SYSTEM_EN = (
    "You are an experienced YouTube scriptwriter who writes in natural spoken English. "
    "You return only valid JSON and nothing else."
)


def _is_en() -> bool:
    return config.CONTENT_LANG.lower().startswith("en")


def _prompt_tr(kind: str, angle: str, recent: list) -> str:
    fmt = config.FORMATS[kind]
    s_lo, s_hi = fmt["scenes"]
    w_lo, w_hi = fmt["words"]
    if kind == "short":
        kind_desc = "YouTube Shorts (dikey, yaklaşık 45-55 saniye, tek bir fikir, güçlü bir kapanış)"
    else:
        kind_desc = (
            "normal YouTube videosu (yatay, yaklaşık 6-8 dakika; giriş, gelişme ve sonuç bölümleri olsun; "
            "somut örnekler ve kısa hikâyeler içersin)"
        )
    recent_txt = "; ".join(recent) if recent else "yok"
    schema = (
        '{"title": "en fazla 70 karakter, merak uyandıran başlık", '
        '"description": "2-3 cümlelik açıklama", '
        '"tags": ["5 ila 10 etiket"], '
        '"scenes": [{"narration": "bu sahnede seslendirilecek metin", '
        '"keywords": "stok video araması için İNGİLİZCE, 2-3 kelime, somut görüntü (ör: sunrise mountain)"}]}'
    )
    return (
        f"Kanal teması: {config.THEME}\n"
        f"Bu videonun açısı: {angle}\n"
        f"Format: {kind_desc}\n"
        f"Sahne sayısı: {s_lo}-{s_hi}. Toplam anlatım uzunluğu: {w_lo}-{w_hi} kelime.\n\n"
        "Kurallar:\n"
        "- Dil: akıcı, doğal, konuşma diline yakın Türkçe. Metin sesli okunacak; rakamları ve kısaltmaları "
        "yazıyla yaz, emoji, hashtag ve yıldız işareti kullanma.\n"
        "- İlk cümle ilk 3 saniyede izleyiciyi yakalayan bir kanca olsun. Son sahne düşündüren bir kapanış olsun.\n"
        "- Gerçek kişilere uydurma alıntı veya uydurma olay atfetme. Hikâye kurgusal ise karakter adını uydur "
        "ve gerçek biriymiş gibi sunma.\n"
        "- Tıbbi, finansal veya kesin sonuç vaat eden iddialarda bulunma.\n"
        "- Her sahnenin keywords alanı farklı ve görselleştirilebilir olsun (insan, doğa, şehir, yol vb.).\n"
        f"- Şu başlıklara benzer içerik üretme: {recent_txt}\n\n"
        f"Yalnızca şu şemaya uyan JSON döndür:\n{schema}"
    )


def _prompt_en(kind: str, angle: str, recent: list) -> str:
    fmt = config.FORMATS[kind]
    s_lo, s_hi = fmt["scenes"]
    w_lo, w_hi = fmt["words"]
    if kind == "short":
        kind_desc = "YouTube Shorts (vertical, about 40-50 seconds, one single idea, a strong closing line)"
    else:
        kind_desc = (
            "a standard YouTube video (horizontal, about 6-8 minutes; with an intro, a body and a conclusion; "
            "include concrete examples and short stories)"
        )
    recent_txt = "; ".join(recent) if recent else "none"
    schema = (
        '{"title": "at most 70 characters, curiosity-sparking title", '
        '"description": "2-3 sentence description", '
        '"tags": ["5 to 10 tags"], '
        '"scenes": [{"narration": "the text spoken in this scene", '
        '"keywords": "ENGLISH stock-video search phrase, 2-3 words, a concrete visual (e.g. sunrise mountain)"}]}'
    )
    return (
        f"Channel theme: {config.THEME}\n"
        f"Angle of this video: {angle}\n"
        f"Format: {kind_desc}\n"
        f"Number of scenes: {s_lo}-{s_hi}. Total narration length: {w_lo}-{w_hi} words.\n\n"
        "Rules:\n"
        "- Language: fluent, natural, conversational English. The text will be read aloud by a voice, so write "
        "numbers and abbreviations as words and do not use emojis, hashtags or asterisks.\n"
        "- The first sentence must be a hook that grabs the viewer in the first 3 seconds. "
        "The last scene must be a thoughtful closing line.\n"
        "- Do not attribute made-up quotes or made-up events to real people. If the story is fictional, invent "
        "the character's name and do not present it as a real person.\n"
        "- Do not make medical or financial claims or promise guaranteed results.\n"
        "- The keywords field of every scene must be different and easy to visualize (people, nature, city, road, etc.).\n"
        f"- Do not create content similar to these titles: {recent_txt}\n\n"
        f"Return only JSON that follows this schema:\n{schema}"
    )


def _prompt(kind: str, angle: str, recent: list) -> str:
    return (_prompt_en if _is_en() else _prompt_tr)(kind, angle, recent)


def _validate(data: dict, kind: str) -> dict:
    fmt = config.FORMATS[kind]
    if not isinstance(data, dict):
        raise ValueError("yanıt beklenen biçimde değil")
    title = str(data.get("title", "")).strip().strip('"')
    if not title:
        raise ValueError("başlık yok")
    raw_scenes = data.get("scenes")
    if not isinstance(raw_scenes, list):
        raise ValueError("sahne listesi beklenen biçimde değil")
    scenes = []
    for s in raw_scenes:
        # Model bazen şemaya uymaz: sahne düz metin ya da [metin, anahtar kelime] listesi olarak gelebilir
        if isinstance(s, (list, tuple)):
            s = {"narration": s[0] if len(s) > 0 else "", "keywords": s[1] if len(s) > 1 else ""}
        elif isinstance(s, str):
            s = {"narration": s}
        elif not isinstance(s, dict):
            continue
        narration = str(s.get("narration", "")).strip()
        keywords = str(s.get("keywords", "")).strip()
        if narration:
            scenes.append({"narration": narration, "keywords": keywords or "nature landscape"})
    if not scenes:
        raise ValueError("sahne yok")
    words = sum(len(s["narration"].split()) for s in scenes)
    lo, hi = fmt["words"]
    if words < lo * 0.75 or words > hi * 1.3:
        raise ValueError(f"kelime sayısı uygunsuz: {words} (beklenen {lo}-{hi})")
    s_lo, s_hi = fmt["scenes"]
    if not (s_lo - 2 <= len(scenes) <= s_hi + 4):
        raise ValueError(f"sahne sayısı uygunsuz: {len(scenes)}")

    raw_tags = data.get("tags") or []
    if isinstance(raw_tags, str):
        raw_tags = raw_tags.split(",")
    if not isinstance(raw_tags, list):
        raw_tags = []
    tags = [str(t).strip().lstrip("#") for t in raw_tags if str(t).strip()]
    return {
        "title": title[:90],
        "description": str(data.get("description", "")).strip(),
        "tags": tags[:10],
        "scenes": scenes,
    }


def generate(kind: str, recent_titles: list, attempts: int = 3) -> dict:
    en = _is_en()
    angle = random.choice(ANGLES_EN if en else ANGLES)
    system = SYSTEM_EN if en else SYSTEM
    print(f"[senaryo] tür={kind} dil={config.CONTENT_LANG} açı='{angle}'")
    last_error = None
    for i in range(attempts):
        try:
            data = llm.generate_json(system, _prompt(kind, angle, recent_titles))
            return _validate(data, kind)
        except (llm.LLMError, ValueError, AttributeError, TypeError, KeyError, IndexError) as e:
            last_error = e
            print(f"[senaryo] deneme {i + 1} başarısız: {e}")
    raise RuntimeError(f"Senaryo üretilemedi: {last_error}")
