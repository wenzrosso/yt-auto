"""Bir kez, kendi bilgisayarınızda çalıştırılır: YouTube yükleme izni verir ve GitHub'a girilecek 3 değeri yazdırır.

Kullanım:
    1) Google Cloud'dan indirdiğiniz OAuth istemci dosyasını bu klasöre client_secret.json adıyla koyun.
    2) python auth_setup.py
    3) Açılan tarayıcıda YouTube kanalının bulunduğu Google hesabıyla izin verin.
"""
import json
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
SECRET_FILE = Path(__file__).parent / "client_secret.json"


def main() -> int:
    if not SECRET_FILE.exists():
        print("client_secret.json bulunamadı. README'deki 3. adıma bakın.")
        return 1
    flow = InstalledAppFlow.from_client_secrets_file(str(SECRET_FILE), SCOPES)
    # offline + consent: Google'ın her seferinde kalıcı bir yenileme anahtarı (refresh token) vermesini sağlar
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    if not creds.refresh_token:
        print("Yenileme anahtarı alınamadı. https://myaccount.google.com/permissions adresinden uygulamaya verilen "
              "izni kaldırıp betiği yeniden çalıştırın.")
        return 1

    info = json.loads(SECRET_FILE.read_text(encoding="utf-8"))
    info = info.get("installed") or info.get("web") or {}
    print("\n=== GitHub > Settings > Secrets and variables > Actions > Secrets bölümüne şunları ekleyin ===\n")
    print(f"YT_CLIENT_ID     = {info.get('client_id')}")
    print(f"YT_CLIENT_SECRET = {info.get('client_secret')}")
    print(f"YT_REFRESH_TOKEN = {creds.refresh_token}")
    print("\nBu değerleri kimseyle paylaşmayın; sahibi olmanız kanalınıza yükleme yapma yetkisi verir.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
