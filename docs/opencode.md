# OpenCode Zen / Jev bağlantısı

Resmî kaynak: https://opencode.ai/docs/zen/#jev (29 Eylül 2026 kontrolü).

- Sağlayıcı: `opencode`
- HTTP: `POST https://opencode.ai/zen/v1/systemone`
- Yetkilendirme: `Authorization: Bearer <OpenCode Zen API anahtarı>`
- İçerik türü: `application/json`
- Model: `jev-1.13-free` (belgede süreli ücretsiz model)
- Gövde: `model`, `state`, `questions`; yanıtta `answers`.

OpenCode uygulaması veya SDK kurulmaz; mevcut Python HTTP istemcisi kullanılır.
Anahtar gizli terminal girişinden alınır. API bağlantı testi başarılı olunca KDE
Secret Service/KWallet kasasında sağlayıcıya özel kaydedilir; sonraki açılışta
buradan alınır. Kasa kullanılamazsa yalnızca oturum belleğinde tutulur. Düz metin
kayıt yapılmaz. `/key` doğrulanan yeni anahtarı kaydeder; `/forget-key` kaydı siler.
Ortam değişkeniyle çalıştırılan tek komutlarda `OPENCODE_API_KEY` kullanılır.
OpenRouter anahtarı bu sağlayıcıya taşınmaz. Başka modele otomatik geçiş yoktur.

## İlk gerçek API testi

```sh
cd /home/ykk/jev-test
./desktop-agent --provider opencode
```

Gizli isteme OpenCode Zen anahtarını girin. CLI istemine `/check` yazın.
Bu komut kısa, sentetik bir metinle Noul sorusu gönderir; hiçbir masaüstü eylemi
uygulamaz. `success: true` ve `api_response_valid: true`, gerçek API yanıtının
geçerli biçimde alındığını gösterir; genel görev doğruluğunu kanıtlamaz.

Bağlantı testi geçince `/listen` yazın. Ctrl+Alt+V basılıyken
“Search YouTube for jazz and scroll down” söyleyin ve bırakın. Bu çok adımlı
komut Jev döngüsüne girer. Tek uygulama/site açma veya tek arama komutları
API'ye gitmediğinden bağlantı testi yerine kullanılamaz.

`AUTHENTICATION_FAILED`: sağlayıcı anahtarı reddetti.
`API_BAD_REQUEST`: sağlayıcı isteği reddetti; yalnızca durum kodundan kesin neden çıkarılamaz.
`INVALID_RESPONSE`: beklenen typed yanıt alınmadı.
`RATE_LIMITED`: API isteği hız sınırına takıldı.

Yerel HTTP sözleşmesi ve CLI testleri geçti. Kullanıcının gerçek anahtarıyla
API denemesi henüz bu geliştirme oturumunda yapılmadı.

403 tanısı: `/check` sonucu `reason` alanı içerir. `FREE_TIER_RESTRICTED`,
sağlayıcının hata türü/mesajında ücretsiz erişim kısıtı belirtildiğini gösterir.
`MODEL_ACCESS_RESTRICTED`, `ACCOUNT_ACCESS_RESTRICTED`, `BILLING_REQUIRED` diğer
tanınan nedenlerdir. `ACCESS_POLICY_UNKNOWN`, yanıtın bu nedenlere sınıflanamadığı
anlamına gelir; anahtarın yanlış olduğu sonucuna varılmaz. Ham yanıt gösterilmez.
Zen reposundaki https://github.com/anomalyco/opencode/issues/49433 kaydı başka
ücretsiz modeller için bu kısıtı bildirir; tek başına Jev’deki hatayı kanıtlamaz.

## HTTP 403 düzeltmesi — sürüm 2026-09-29.4

Aynı sentetik istekte varsayılan Python-urllib başlığı 403 ve düz metin
`error code: 1010` döndürdü. Uygulamayı doğru tanıtan
`User-Agent: JevDesktopAgent/2026.09 (Python urllib)` ile HTTP 200 ve geçerli
Jev yanıtı alındı. Bu başlık gerçek istemciye eklendi.
https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-1xxx-errors/error-1010/

Düzeltilmiş istemciyle anonim `public` erişim üzerinden gerçek `/check` testi
geçti: model `jev-1.13-free`, Noul 0.99. Kullanıcının özel anahtarı okunmadı.
Gerçek Jev seçimli sentetik Firefox testinde beş eylemin etkisi doğrulandı;
son DONE seçimi güven eşiğini geçmediğinden tüm görev testi başarılı sayılmadı.
İkinci deneme aktif pencere değiştiği için ilerlemedi. Eylem geçmişine liste
seçeneği ve kaydırma yönü eklendi. 57 birim testi geçti.

Sürüm 2026-09-29.5: OpenCode artık varsayılandır. `./desktop-agent` metin,
`./desktop-agent listen` sesli moddur; provider bayrağı gerekmez. Anahtar
girildikten sonra gerçek bağlantı testi otomatik çalışır. Test başarısızsa
başlangıçta dinleme başlamaz. 59 birim testi geçti.

Sürüm 2026-09-29.6: Ctrl+Alt+J doğrudan sesli modu açar. Doğrulanmış anahtar
güvenli kasada hatırlanır. Tarayıcı kapanınca sonraki gezinmede bağlantı yenilenir.
