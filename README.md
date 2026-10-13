# YouTube Otomatik Video Sistemi

Her 3 saatte bir kendiliğinden çalışır: yapay zeka senaryo yazar, doğal Türkçe sesle seslendirir, ücretsiz stok görüntülerle videoyu birleştirir, altyazıyı gömer ve YouTube'a yükler. Çalışma yeri **GitHub Actions** olduğu için bilgisayarınızın açık olması gerekmez.

- **Shorts** (dikey, ~50 sn) ve **normal video** (yatay, ~6-8 dk) birlikte üretilir. Varsayılan düzen: günde 8 çalıştırmadan 2'si normal video (Türkiye saatiyle 09:00 ve 21:00), 6'sı Shorts.
- Konu: motivasyon ve kısa hikâyeler. Konuyu değiştirmek için `CHANNEL_THEME` ayarı yeterli.
- Maliyet: Gemini ücretsiz kotası, edge-tts, Pixabay (veya Pexels) ve GitHub Actions ile 0 TL.

## Başlamadan önce bilmeniz gerekenler

1. **YouTube API günlük kotası yaklaşık 6 yükleme.** Bir yükleme 1600 birim harcar, varsayılan günlük kota 10.000 birimdir. 3 saatte bir = günde 8 video olduğu için sistem varsayılan olarak günde **6** ile durur (`MAX_UPLOADS_PER_DAY`). 8'e çıkmak için Google'dan kota artışı istemeniz gerekir (bkz. "Kota artışı").
2. **Yeni API projesiyle yüklenen videolar özel (private) kalabilir.** Google, doğrulanmamış API projelerinde yüklenen videoları denetim yapılana kadar kilitleyebilir. Bu yüzden ilk günlerde videoların gizli kalması normal olabilir; çözümü "Kota artışı" bölümündeki denetim formudur.
3. **Yapay zeka ile toplu üretilen içerik gelir kazanmayı zorlaştırabilir.** YouTube, tekrar eden ve toplu üretilmiş içerikleri "özgün olmayan içerik" saydığında Ortaklık Programı'na kabulü veya geliri etkileyebilir. Videoların birbirinden gerçekten farklı olması, kısa ama kaliteli kalması ve ara sıra sonuçlara bakıp ayarları düzeltmeniz önemli.
4. Gerçek kişiymiş gibi görünen sentetik ses/görüntü kullanırsanız YouTube'da "değiştirilmiş içerik" işaretlemesi gerekir. Bu sistem genel bir yapay zeka sesi ve stok görüntü kullanır; yine de gerekirse `CONTAINS_SYNTHETIC_MEDIA=true` yapabilirsiniz. Açıklamaya otomatik olarak "seslendirme yapay zekâ ile oluşturulmuştur" notu eklenir.

## Kurulum (yaklaşık 30-40 dakika, tek seferlik)

### 1) Hesaplar ve anahtarlar (hepsi ücretsiz)

- **GitHub hesabı:** github.com
- **Gemini API anahtarı:** aistudio.google.com/apikey adresinden "Create API key". Senaryoyu bu yazar.
- **Pixabay API anahtarı:** pixabay.com'da ücretsiz hesap açın. Giriş yaptıktan sonra pixabay.com/api/docs/ sayfasında anahtarınız görünür. Stok videolar buradan gelir. Alternatif olarak pexels.com/api adresinden Pexels anahtarı da kullanılabilir; ikisinden en az biri yeterlidir (Pexels bu projenin yazıldığı sırada yeni anahtar vermeyi geçici olarak durdurmuştu).
- Videoların yükleneceği **YouTube kanalı** (kanalı olan Google hesabı).

### 2) GitHub deposu

1. GitHub'da yeni bir depo (repository) oluşturun. **Public** (herkese açık) öneririm: standart Actions çalıştırıcıları herkese açık depolarda ücretsiz ve sınırsızdır. Anahtarlarınız "Secrets" içinde saklanır, depoyu herkese açık yapmak onları ifşa etmez. Açık olan tek şey `state/history.json` içindeki video başlıkları olur.
2. Bu klasördeki **tüm dosyaları** (`.github` klasörü dahil) depoya yükleyin. Bilgisayarınızda git kullanmak istemezseniz GitHub'ın web arayüzünden "Add file > Upload files" ile sürükleyip bırakabilirsiniz. `.github` gizli klasör olduğu için görünmeyebilir; dosya yöneticinizde gizli dosyaları göster seçeneğini açın.

### 3) YouTube yükleme izni (en hassas adım)

1. console.cloud.google.com adresinde yeni bir **proje** oluşturun.
2. **APIs & Services > Library** bölümünde "YouTube Data API v3" arayıp **Enable** deyin.
3. **OAuth consent screen** (Google Auth Platform) bölümünü doldurun: kullanıcı türü **External**, uygulama adı ve e-posta alanlarını yazın. Kapsam (scope) olarak `.../auth/youtube.upload` ekleyin.
4. **Önemli:** Yayın durumunu **"In production"** yapın (Publish app). "Testing" modunda bırakırsanız yenileme anahtarı **7 gün sonra geçersiz olur** ve sistem bir hafta sonra sessizce durur. Doğrulama istemeden kendi kullanımınız için "In production" yapabilirsiniz; giriş sırasında çıkan "Google bu uygulamayı doğrulamadı" uyarısında **Advanced > Go to ... (unsafe)** seçeneğiyle devam edin. Uygulama sizin olduğu için güvenlidir.
5. **Credentials > Create credentials > OAuth client ID** deyin, tür olarak **Desktop app** seçin ve JSON dosyasını indirin. Dosya adını `client_secret.json` yapıp bu klasöre koyun (depoya yüklemeyin, `.gitignore` zaten engeller).

### 4) Yenileme anahtarını alma (kendi bilgisayarınızda, bir kez)

Python 3.10 veya üstü kurulu olmalı (python.org). Bu klasörde bir terminal açıp:

```
pip install -r requirements.txt
python auth_setup.py
```

Tarayıcı açılır; **YouTube kanalının bulunduğu Google hesabıyla** izin verin. Terminal size 3 değer yazdırır: `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`.

### 5) GitHub'a anahtarları ekleme

Depoda **Settings > Secrets and variables > Actions > New repository secret** ile şunları ekleyin:

| Secret | Değer |
|---|---|
| `GEMINI_API_KEY` | Gemini anahtarı |
| `PIXABAY_API_KEY` | Pixabay anahtarı (Pexels anahtarınız varsa ayrıca `PEXELS_API_KEY` de eklenebilir) |
| `YT_CLIENT_ID` | auth_setup.py çıktısı |
| `YT_CLIENT_SECRET` | auth_setup.py çıktısı |
| `YT_REFRESH_TOKEN` | auth_setup.py çıktısı |

### 6) Test

1. Depoda **Actions** sekmesine girin (ilk seferde iş akışlarını etkinleştirmeniz istenebilir).
2. "Video üret ve YouTube'a yükle" > **Run workflow**. Önce `kind=short` ve **"Yükleme, sadece üret" kutusu işaretli** seçin. Çalışma yeşil biterse senaryo, ses ve video üretimi çalışıyor demektir.
3. Şimdi aynısını kutuyu **işaretlemeden** çalıştırın. Video kanalınıza **özel (private)** olarak yüklenir. YouTube Studio'dan izleyip kalitesinden memnun kalın.
4. Memnunsanız **Settings > Secrets and variables > Actions > Variables** bölümünde `PRIVACY_STATUS` = `public` oluşturun. Bundan sonra videolar herkese açık yüklenir ve 3 saatte bir kendiliğinden çalışmaya devam eder.

## Ayarlar (Variables, hepsi isteğe bağlı)

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `PRIVACY_STATUS` | `private` | `public` yapınca herkese açık yüklenir |
| `MAX_UPLOADS_PER_DAY` | `6` | Kota artışından sonra `8` yapın |
| `LONG_SLOTS` | `2,6` | Normal video üretilecek 3 saatlik dilimler (UTC saat/3). `2,6` = 09:00 ve 21:00 (TR) |
| `CHANNEL_THEME` | motivasyon ve ilham veren kısa hikâyeler | Kanal konusu |
| `TTS_VOICE` | `tr-TR-AhmetNeural` | Kadın sesi için `tr-TR-EmelNeural` |
| `LLM_PROVIDER` | `gemini` | `anthropic` seçerseniz `ANTHROPIC_API_KEY` secret'ı gerekir (ücretli) |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Model kaldırılırsa güncel bir Flash modeliyle değiştirin |
| `CONTAINS_SYNTHETIC_MEDIA` | `false` | "Değiştirilmiş/sentetik içerik" işareti |

**Fon müziği:** `assets/music` klasörüne telif sorunu olmayan MP3 dosyaları koyarsanız videolara kısık sesle eklenir (YouTube Stüdyo > Ses Kitaplığı'ndan ücretsiz indirebilirsiniz). Klasör boşsa müzik eklenmez.

## Kota artışı ve denetim

YouTube API Services için "Audit and Quota Extension Form" başvurusu yapmanız gerekir (Google'da bu adla aratın). Formda projenizin ne yaptığını, günde kaç video yükleyeceğinizi anlatırsınız. Onaylanınca hem yüklemelerin kilitli (private) kalması sorunu çözülür hem de günlük kota artar. Onay süresi değişkendir; bu sürede günde 6 ve altıyla çalışmaya devam edebilirsiniz.

## Tahmini Actions süresi

Ölçmedim, tahminidir: Shorts ~3-5 dk, normal video ~10-15 dk. Günlük toplam yaklaşık 50 dakika eder. Depo **public** ise ücretsizdir. **Private** yaparsanız ücretsiz plandaki aylık dakika kotası (güncel miktarı GitHub faturalandırma sayfasından kontrol edin) sınırda kalabilir.

## Sorun giderme

- **Çalışma kırmızı bitti:** Actions > ilgili çalışma > günlükte hata satırına bakın. En sık nedenler: yanlış/eksik secret, Gemini modelinin kaldırılması (`GEMINI_MODEL`), stok video servisinin kotası.
- **"Bugün ... video yüklendi; sınır ..." mesajı:** Günlük sınırın dolduğu anlamına gelir, hata değildir. Sayım, YouTube kotasının sıfırlandığı Pasifik saatine göre yapılır.
- **Bir hafta sonra durdu / `invalid_grant`:** Adım 3.4'teki "In production" yapılmamıştır. Yapıp `auth_setup.py` ile yeni bir yenileme anahtarı alın.
- **Zamanlanmış çalışmalar durdu:** GitHub, 60 gün boyunca etkinlik olmayan herkese açık depolarda zamanlanmış çalışmaları kapatabilir. Actions sekmesinden yeniden etkinleştirin.
- **Seslendirme (edge-tts) başarısız olursa** sistem otomatik olarak gTTS'e geçer; ses kalitesi biraz daha düşük olur.
- **GitHub'ın zamanlayıcısı birkaç dakika gecikebilir,** saat tam 3 saatte bir olmayabilir. Bu normaldir.

## Bilgisayarınızda deneme (isteğe bağlı)

```
python main.py --dry-run     # internetsiz deneme videosu üretir (output/ klasörüne)
python main.py --no-upload   # gerçek içerik üretir ama yüklemez
```

Gerekenler: Python, ffmpeg ve `pip install -r requirements.txt`. `--no-upload` için ayrıca `GEMINI_API_KEY` ile `PIXABAY_API_KEY` (veya `PEXELS_API_KEY`) ortam değişkenleri tanımlı olmalı.
