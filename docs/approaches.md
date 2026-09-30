# Jev ile sesli masaüstü kontrolü — 29 Eylül 2026

## İncelenen kaynaklar

| Repo | Yaklaşım | Bu projeye etkisi |
| --- | --- | --- |
| [kevinbadi/jev-voice](https://github.com/kevinbadi/jev-voice) | Yerel whisper.cpp, ses etkinliği ile konuşma sonu, uyandırma kelimesi; komut metninden adaylar ve Jev Choice. Masaüstü döngüsünde güncel erişilebilirlik hedefleri. | Ses girişini karar katmanından ayır; yazılacak metni üretmek yerine komuttan seç. macOS yürütücüsü Linux'a doğrudan uymaz. |
| [savka777/jev-use](https://github.com/savka777/jev-use) | Erişilebilirlik ağacı → hedef seçimi → eylem → yeniden okuma. Bas-konuş ve uyandırma kelimesi. | Her eylem sonrası gerçek etkiyi oku; düşük güven ve hassas işlemlerde dur. Apple Speech yerel Linux STT yerine kullanılamaz. |
| [browser-use/jev-ultrafast](https://github.com/browser-use/jev-ultrafast) | Güncel DOM hedefleri; tek istekte operasyon ve uygun hedef soruları. Serbest yazı gerektiğinde ayrı küçük metin modeli. | Tarayıcı görevlerinde DOM adaptörü; eski hedefi kullanma, DONE sonucunu bağımsız doğrula. README'deki hız sonuçları genel güvenilirlik kanıtı değildir. |
| [coco-research/jev-use](https://github.com/coco-research/jev-use) | Yetenek kayıt defteriyle model gerektirmeyen yollar; Jev gerektiğinde seçim yapar. Rust/macOS erişilebilirlik katmanı. | Bilinen eylemleri deterministik araçlara bağla; model ile yürütücüyü ayrı tut. |

README'ler ve jev-voice'un karar/ajan/masaüstü kaynakları çevrimiçi okundu.
Bu repolar klonlanmadı, kurulmadı veya yerel olarak çalıştırılmadı.

## Seçilen mimari

Son kullanıcı düzeltmesi: fan/çevre sesi nedeniyle varsayılan giriş `hold`
oldu. Ctrl+Alt+V basılıyken kayıt, bırakınca STT/eylem. Uyandırma kelimesi
isteğe bağlı mod olarak korunuyor. Ekran göstergesi kayıt durumunu gösteriyor.

PipeWire mikrofon → yerel Whisper → OpenRouter/Jev →
kodun sunduğu eylem/hedef → yürütme → gerçek durum kontrolü.

Uyandırma kelimesi özel bir akustik modelle değil, yerel transkriptin başında
aranır. Bu nedenle Whisper gecikmesi vardır; “Jev” farklı yazılırsa komut kaçabilir.
“Jeff” ve “Jef” alternatifleri kabul edilir. Arka plan konuşması API'ye gönderilmez.
Eylem sırasında mikrofon kapalıdır; işlem bitince yeni komut dinlenir.

Jev görüntü/ses okuyamaz ve serbest metin üretemez. Ekran kontrolü için Linux'ta
AT-SPI, tarayıcıda DOM gibi metin gözlemleri gerekir. Bunlar olmadan “her görevi
yapar” iddiası kurulamaz. Bu sürüm ikinci bir metin modeli kullanmaz; yazılacak içerik yalnızca komuttan alınır.

## Bu makinedeki bulgular

- `parec`, `pw-record`, `wpctl`, `ffmpeg`, `cmake`, C++ derleyicisi hazır.
- İlk incelemede Whisper/model yoktu. Sonradan açık indirme onayıyla
  whisper.cpp v1.9.4 ve base.en proje içinde kuruldu; faster-whisper kurulmadı.
- GI/AT-SPI arayüzü mevcut. Erişilebilirlik etkinleştirilerek gerçek Qt test penceresinde
  yazma ve tıklama doğrulandı. Firefox için ayrı profil ve DOM/Marionette kullanıldı.
- İlk metin → uygulama yolu kullanıcı tarafından OpenRouter anahtarıyla doğrulandı.

## Uygulanan döngü ve doğrulama

Gizli API anahtarı, yerel STT, bas-konuş ve durum göstergesi korunarak genel döngü eklendi:

1. Aktif pencere ve güncel AT-SPI/DOM hedefleri okunur.
2. Jev kapalı operasyon/hedef/metin/URL seçeneklerinden seçim yapar.
3. Hedefin güncelliği, görünürlüğü ve aktif pencere kontrol edilir.
4. Kod eylemi uygular; arayüz tekrar okunur ve görülen etki kaydedilir.
5. Süre, adım ve ilerlemesiz tekrar sınırları döngüyü durdurur.

Silme, gönderme ve satın alma gibi işlemler onay ister. Shell, model üretimi JavaScript,
koordinat ve yeni metin kabul edilmez. Hassas alanlar hedef listesine alınmaz.
Jev DONE seçse bile genel görev için bağımsız başarı kanıtı varsayılmaz;
CLI `goal_verified: false` sonucunu açıklar.

47 birim testi geçti. Gerçek KDE/AT-SPI testinde yazma ve düğmeye basma,
RemoteDesktop portalıyla Ctrl+T etkisi doğrulandı. Gerçek Firefox/DOM testinde
gezinti → yazma → tıklama → liste seçimi → kaydırma uygulandı; eski hedef reddi
ve parola alanının dışlanması kontrol edildi. Çok adımlı test çevrimdışı bir seçim
politikası kullanır; gerçek Jev genel görev denemesi bunun yerine geçmez.
Kullanıcı gerçek ses → Jev → tarayıcı açma akışını doğruladı.

## Ek birincil kaynaklar

- [Firefox Marionette protokolü](https://firefox-source-docs.mozilla.org/remote/marionette/Protocol.html):
  mevcut Firefox üzerinden yerel DOM gözlemi ve denetimli eylemler; ek sürücü indirilmedi.
- [RemoteDesktop portalı](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.RemoteDesktop.html):
  KDE onayıyla klavye/fare kontrolü.
- [whisper.cpp](https://github.com/ggml-org/whisper.cpp): İngilizce base.en ile yerel çözümleme.
  Kaynak ve model yalnızca önceki indirme onayıyla `.local/` içine kuruldu.

Bu genişletme sırasında paket, repo veya model indirilmedi.

## Gerçek komut hatasından sonra düzeltme

Kullanıcı testinde Jev gezinme operasyonu için blocked seçti. Kod incelemesinde
operasyon sorusunda URL ve araç bilgilerinin eksik olduğu görüldü; modelin seçim
nedeni yanıtında açıklanmaz. Operasyon sorusuna somut URL adayları ve aracın
kendi Firefox’unu başlatabildiği eklendi. [API belgesine](https://docs.typesafe.ai/api)
göre soru anahtarı modele gönderilmez; gerekli anlam talimat ve verilerde bulunur.

Kesin yapılandırılmış uygulama/site/arama istekleri doğrudan araçlara bağlandı;
çok adımlı görevler model döngüsünde kaldı. Dört kullanıcı komutu gerçek masaüstünde
API anahtarı olmadan başarıyla doğrulandı. Genel görevlerin gerçek Jev seçiminin
başarısı bu testten çıkarılamaz. %80 eşikleri korunur; yeni indirme yapılmadı.

Ücretsiz model düzeltmesi: OpenCode Zen’in resmî belgesi `jev-1.13-free` için
`https://opencode.ai/zen/v1/systemone` ve kendi API anahtarını tanımlar. OpenRouter
ile bu kimliği eşleştirmek yanlıştı. Ayrı `opencode` sağlayıcısı eklendi; yanlış
eşleştirme ağ çağrısından önce durur. Gerçek anahtar testi bekler; 50 test geçti.
