"""Senaryo üretimi için yapay zeka çağrıları (Gemini veya Anthropic), ek kütüphane gerektirmez."""
import json
import os
import re
import time

import requests

from . import config


class LLMError(RuntimeError):
    pass


def _post(url: str, headers: dict, payload: dict, tries: int = 4) -> dict:
    last = "bilinmeyen hata"
    for i in range(tries):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=180)
        except requests.RequestException as e:
            last = str(e)
            time.sleep(5 * (i + 1))
            continue
        if r.status_code in (429, 500, 502, 503, 504):
            last = f"HTTP {r.status_code}: {r.text[:200]}"
            time.sleep(8 * (i + 1) ** 2)
            continue
        if r.status_code >= 400:
            raise LLMError(f"HTTP {r.status_code}: {r.text[:400]}")
        return r.json()
    raise LLMError(f"İstek {tries} denemede başarısız oldu: {last}")


def _gemini(system: str, prompt: str, max_tokens: int) -> str:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise LLMError("GEMINI_API_KEY tanımlı değil.")
    model = config.GEMINI_MODEL
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    gen_cfg = {
        "temperature": 1.0,
        "maxOutputTokens": max_tokens,
        "responseMimeType": "application/json",
    }
    if "2.5" in model and "flash" in model:
        gen_cfg["thinkingConfig"] = {"thinkingBudget": 0}  # düşünme jetonları çıktıyı kesmesin
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": gen_cfg,
    }
    data = _post(url, {"x-goog-api-key": key}, payload)
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError):
        raise LLMError(f"Beklenmeyen Gemini yanıtı: {str(data)[:300]}")


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


def generate_json(system: str, prompt: str, max_tokens: int = 8192) -> dict:
    if config.LLM_PROVIDER == "anthropic":
        raw = _anthropic(system, prompt, max_tokens)
    else:
        raw = _gemini(system, prompt, max_tokens)
    return parse_json(raw)
