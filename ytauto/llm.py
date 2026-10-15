"""Senaryo üretimi için yapay zeka çağrıları (Gemini veya Anthropic), ek kütüphane gerektirmez."""
import json
import os
import re
import time
from typing import Optional

import requests

from . import config

# Ayarlanan model kullanılamazsa (404) sırayla bunlar denenir. Google eski modelleri yeni hesaplara kapatabilir.
GEMINI_FALLBACKS = ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite"]
_working_model: Optional[str] = None  # bu çalışmada işe yarayan model, tekrar 404 yememek için


class LLMError(RuntimeError):
    def __init__(self, message: str, status: Optional[int] = None):
        super().__init__(message)
        self.status = status


RETRY_CODES = (429, 500, 502, 503, 504)
# Bu hatalarda aynı modelden vazgeçip sıradaki modele geçilir (404: model yok, 599: bağlantı/zaman aşımı)
FAILOVER_CODES = {404, 429, 500, 502, 503, 504, 599}


def _post(url: str, headers: dict, payload: dict, tries: int = 3, timeout: int = 75) -> dict:
    last, last_status = "bilinmeyen hata", None
    for i in range(tries):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=timeout)
        except requests.RequestException as e:
            last, last_status = f"{type(e).__name__}: {str(e)[:150]}", 599
            print(f"[llm] bağlantı sorunu ({type(e).__name__}), deneme {i + 1}/{tries}")
        else:
            if r.status_code in RETRY_CODES:
                last, last_status = f"HTTP {r.status_code}: {r.text[:150]}", r.status_code
                print(f"[llm] sunucu meşgul veya sınırda (HTTP {r.status_code}), deneme {i + 1}/{tries}")
            elif r.status_code >= 400:
                raise LLMError(f"HTTP {r.status_code}: {r.text[:400]}", status=r.status_code)
            else:
                return r.json()
        if i < tries - 1:
            time.sleep(5 * (i + 1))
    raise LLMError(f"İstek {tries} denemede başarısız oldu: {last}", status=last_status)


def _thinking_cfg(model: str) -> Optional[dict]:
    """Düşünme jetonları çıktı sınırından yer yer; JSON kesilmesin diye düşünmeyi en aza indiririz."""
    if "2.5" in model and "flash" in model:
        return {"thinkingBudget": 0}
    if model.startswith("gemini-3"):
        return {"thinkingLevel": "low"}
    return None


def _gemini_call(key: str, model: str, system: str, prompt: str, max_tokens: int) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    gen_cfg = {
        "temperature": 1.0,
        "maxOutputTokens": max_tokens,
        "responseMimeType": "application/json",
    }
    thinking = _thinking_cfg(model)
    if thinking:
        gen_cfg["thinkingConfig"] = thinking
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": gen_cfg,
    }
    headers = {"x-goog-api-key": key}
    try:
        data = _post(url, headers, payload)
    except LLMError as e:
        # Düşünme ayarı bu modelde kabul edilmediyse ayarsız bir kez daha dene
        if e.status == 400 and thinking and "think" in str(e).lower():
            print(f"[llm] {model} düşünme ayarını kabul etmedi, ayarsız deneniyor")
            gen_cfg.pop("thinkingConfig", None)
            data = _post(url, headers, payload)
        else:
            raise
    try:
        cand = data["candidates"][0]
        parts = cand["content"]["parts"]
    except (KeyError, IndexError, TypeError):
        raise LLMError(f"Beklenmeyen Gemini yanıtı: {str(data)[:300]}")
    text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    if not text.strip():
        raise LLMError(f"Gemini boş yanıt döndürdü (bitiş nedeni: {cand.get('finishReason')})")
    return text


def _gemini(system: str, prompt: str, max_tokens: int) -> str:
    global _working_model
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise LLMError("GEMINI_API_KEY tanımlı değil.")
    candidates = []
    for m in [_working_model, config.GEMINI_MODEL] + GEMINI_FALLBACKS:
        if m and m not in candidates:
            candidates.append(m)
    last: Optional[LLMError] = None
    deadline = time.monotonic() + 420  # toplam en fazla ~7 dakika bekle
    for model in candidates:
        if last is not None and time.monotonic() > deadline:
            print("[llm] süre doldu, daha fazla model denenmiyor")
            break
        try:
            text = _gemini_call(key, model, system, prompt, max_tokens)
        except LLMError as e:
            if e.status in FAILOVER_CODES:
                print(f"[llm] {model} kullanılamadı (HTTP {e.status}), sıradaki model deneniyor")
                last = e
                continue
            raise
        if model != config.GEMINI_MODEL and model != _working_model:
            print(f"[llm] '{model}' modeli kullanılıyor. Kalıcı yapmak için GEMINI_MODEL değişkenini bu değere ayarlayın.")
        _working_model = model
        return text
    raise last or LLMError("Hiçbir Gemini modeli kullanılamadı.")


def _anthropic(system: str, prompt: str, max_tokens: int) -> str:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise LLMError("ANTHROPIC_API_KEY tanımlı değil.")
    payload = {
        "model": config.ANTHROPIC_MODEL,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
    }
    headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
    data = _post("https://api.anthropic.com/v1/messages", headers, payload)
    try:
        return "".join(b.get("text", "") for b in data["content"])
    except (KeyError, TypeError):
        raise LLMError(f"Beklenmeyen Anthropic yanıtı: {str(data)[:300]}")


def parse_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise LLMError("Yanıtta JSON bulunamadı.")
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as e:
        raise LLMError(f"JSON çözümlenemedi: {e}")


def generate_json(system: str, prompt: str, max_tokens: int = 16384) -> dict:
    if config.LLM_PROVIDER == "anthropic":
        raw = _anthropic(system, prompt, max_tokens)
    else:
        raw = _gemini(system, prompt, max_tokens)
    return parse_json(raw)
