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


def _prompt(kind: str, angle: str, recent: list) -> str:
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
    angle = random.choice(ANGLES)
    print(f"[senaryo] tür={kind} açı='{angle}'")
    last_error = None
    for i in range(attempts):
        try:
            data = llm.generate_json(SYSTEM, _prompt(kind, angle, recent_titles))
            return _validate(data, kind)
        except (llm.LLMError, ValueError, AttributeError, TypeError, KeyError, IndexError) as e:
            last_error = e
            print(f"[senaryo] deneme {i + 1} başarısız: {e}")
    raise RuntimeError(f"Senaryo üretilemedi: {last_error}")
