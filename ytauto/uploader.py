"""YouTube Data API v3 ile video yükleme (yenileme anahtarıyla, tarayıcı gerektirmez)."""
import os
import time
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from . import config

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


class QuotaExceeded(RuntimeError):
    pass


def _service():
    for name in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"):
        if not os.environ.get(name):
            raise RuntimeError(f"{name} tanımlı değil (GitHub Secrets'a eklenmeli).")
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def _insert(yt, body: dict, path: Path) -> str:
    media = MediaFileUpload(str(path), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True)
    request = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    response, retries = None, 0
    while response is None:
        try:
            _, response = request.next_chunk()
        except HttpError as e:
            if e.resp.status in (500, 502, 503, 504) and retries < 5:
                retries += 1
                time.sleep(2**retries)
                continue
            raise
        except (ConnectionError, TimeoutError):
            if retries < 5:
                retries += 1
                time.sleep(2**retries)
                continue
            raise
    return response["id"]


def upload(path: Path, title: str, description: str, tags: list, privacy: str) -> str:
    yt = _service()
    clean = lambda s: s.replace("<", "").replace(">", "")
    tag_list, total = [], 0
    for t in tags:
        t = clean(t)[:30]
        if t and total + len(t) < 450:
            tag_list.append(t)
            total += len(t) + 1
    body = {
        "snippet": {
            "title": clean(title)[:100],
            "description": clean(description)[:4900],
            "tags": tag_list,
            "categoryId": config.CATEGORY_ID,
            "defaultLanguage": config.CONTENT_LANG,
            "defaultAudioLanguage": config.CONTENT_LANG,
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": config.SYNTHETIC_MEDIA,
        },
    }
    try:
        return _insert(yt, body, path)
    except HttpError as e:
        text = str(e)
        if "quotaExceeded" in text or "uploadLimitExceeded" in text:
            raise QuotaExceeded(
                "YouTube günlük API kotası ya da günlük yükleme sınırı doldu. "
                "MAX_UPLOADS_PER_DAY değerini düşürün veya kota artışı isteyin."
            )
        if "containsSyntheticMedia" in text:  # alan bu API sürümünde kabul edilmezse onsuz dene
            body["status"].pop("containsSyntheticMedia", None)
            return _insert(yt, body, path)
        raise
