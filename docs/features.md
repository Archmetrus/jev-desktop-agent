# Yeni yetenekler · 2026-09-29.12

Ctrl+Alt+J ile uygulamayı yeniden açın. Önceden çalışan süreç eski kodu kullanır.
Jev veya Laya seçebilirsiniz; aşağıdaki tanımlı komutlar aynı yerel işlem katmanına
gider ve model/API çağrısı yapmaz. Rutin veya öğretilen komut içindeki genel bir
görev ise seçilen modeli kullanabilir.

`/features` bütün yeni komutları gösterir. `/panel` veya sesle `Open control panel`
kontrol panelini açar. Paneli doğrudan açmak için:

```sh
./desktop-agent --provider laya --device cuda panel
```

## 1. Müzik ve video

`Play music`, `Pause music`, `Pause video`, `Resume video`, `Next track`,
`Previous track`, `Stop music`, `Toggle playback`.

Uygulamanın MPRIS sunması gerekir. Önce tek oynayan uygulama seçilir; birden fazla
oynayan uygulama varsa rastgele seçim yapılmaz (`AMBIGUOUS_MEDIA_PLAYER`).
Oynatıcı sonraki/önceki işlemini desteklemiyorsa işlem reddedilir. Komutun
iletildiği ve oynatma durumunun doğrulandığı ayrı alanlarda raporlanır.
[MPRIS işlemleri](https://specifications.freedesktop.org/mpris/latest/Player_Interface.html).

## 2. Sekmeler

`List tabs`, `New tab`, `Close tab`, `Switch tab to "YouTube"` veya `/tabs`.

Yalnızca ajan tarafından açılan görev Firefox'una uygulanır. Başlık tam
veya tek bir kısmi eşleşme olmalıdır. Sekme işlemleri
sabit görev Firefox oturumuna iletilir; terminalden de kullanılabilir. Diğer
tarayıcıların sekmelerine işlem yapılmaz.

## 3–4. Rutinler ve komut öğretme

```text
/routine add work = Open Firefox ; Open Konsole ; Open Dolphin
Run routine work
/routine list
/routine delete work
/teach start coding = Run routine work
start coding
/aliases
/forget start coding
```

Rutin en fazla 8 adım içerir. Hata, onay reddi veya iptal durumunda sonraki adım
çalışmaz. İç içe rutin ve döngülü komut eşlemeleri engellenir. Komutlar normal
hedef ve onay kontrollerinden geçer. Terminale serbest kabuk komutu gönderilmez.
Tanımlar `.state/features/settings.json` içinde, kullanıcıya özel izinle saklanır;
API anahtarları bu dosyaya kaydedilmez.

## 5. Dosyalar

```text
Open file "~/Documents/report.pdf"
Find files "report" in "~/Documents"
Create folder "~/Documents/new folder"
Rename file "~/Documents/report.pdf" to "report-v2.pdf"
Move file "~/Documents/report-v2.pdf" to "~/Downloads/report-v2.pdf"
Trash file "~/Downloads/report-v2.pdf"
```

Boşluk içeren yolları çift tırnak içinde yazın. Varsayılan kökler proje klasörü,
Documents, Downloads, Music, Videos, Pictures, Desktop'tur. Gizli dosyalar ve
projenin `.local`, `.state`, `.git`, `.codex`, `.agents` dizinleri korunur.
Çalıştırılabilir dosyalar bu yoldan başlatılmaz. Son bileşeni sembolik bağlantı
olan dosya taşınmaz/yeniden adlandırılmaz/çöpe gönderilmez. Sembolik bağlantı üzerinden
izin verilen köklerin dışına çıkılamaz. Kök klasörlerin kendisi taşınamaz/silinemez.

Taşıma atomik olarak mevcut hedefin üzerine yazmadan yapılır; farklı diskler
arasındaki taşıma desteklenmez. Çöp kutusu işlemi onay ister; kalıcı silme yoktur.
Arama en fazla 10.000 ad/100 sonuç tarar; dosya içeriğini modele göndermez.

## 6–8. Pencereler, numaralar, geçmiş

`Maximize window`, `Minimize window`, `Tile window left`, `Tile window right`,
`Restore window`, `Move window to desktop 2` aktif pencereye uygulanır.
Mevcut sanal masaüstleri kullanılır; yeni masaüstü oluşturulmaz.

`Show targets` veya `/targets` görünür tıklanabilir hedefleri numaralandırır.
Görev Firefox'unda sayfanın üzerine işaretler; diğer uygulamalarda numaralı
liste gösterir. `Click number two` veya `Click number 2` hedefi seçer. Ekran veya
aktif pencere değişmişse eski liste reddedilir; yeniden `Show targets` deyin.
Numaralar erişilebilirlik/DOM tarafından sunulan hedefler içindir; erişilebilir
hedefi olmayan kontrolleri koordinatla tahmin etmez.

`/history` eylem ve sonuç geçmişini gösterir. Son 200 kayıt yerelde saklanır;
konuşulan/yazılan metin, URL, ekran içeriği ve anahtarlar bu kayda konmaz.
`Undo last action` veya `/undo`, bu oturumdaki en son geri alınabilir işlemi
tersine çevirir: dosya taşıma/yeniden adlandırma, boş klasör oluşturma veya pencere
düzenleme. Dosya/pencere sonradan değişmişse geri alma reddedilir. Tıklama,
gönderme, sekme kapatma ve çöp kutusu işlemleri otomatik geri alınmaz.

## 9. Türkçe

Kullanıcı talebiyle ertelendi. İngilizce Whisper/Laya kullanılıyor; model indirilmedi.

## 10–11. Panel ve durdurma

Panel sağlayıcı ve CPU/CUDA seçimini, komut girişini, duyulan komutu, geçmişi,
mikrofon durumunu ve durdurmayı bir araya getirir. Sağlayıcı değişimi boşta
uygulanır. API sağlayıcısı için güvenli kasada anahtar yoksa terminalde ilgili
sağlayıcıyla açıp `/key` kullanın. Panelde yeni model/paket indirilmez.

Bas-konuş dinlemesinde **Ctrl+Alt+X** kaydı veya görevin bekleyen adımlarını
iptal eder. KDE yeni durdurma kısayolunu da onaylamanızı isteyebilir.
Panelin **Durdur** düğmesi metin ve ses görevlerinde kullanılır. `/stop` metin
komutudur. Yerel model beklerken iptal kontrolü yapılır. API isteği iptal sonrası
sunucuda tamamlanabilir; yanıtı eyleme dönüşmez. Devam eden ağ isteği bitmeden
ikinci genel istek başlatılmaz (`API_REQUEST_PENDING`). Başlamış/tamamlanmış
masaüstü işlemi iptal tarafından geri çevrilmez.

## 12. Çıkış sesi

`Set volume to 40`, `Mute audio`, `Unmute audio`, `List audio outputs`,
`Use audio output 2` veya `/outputs`.

Çıkış seviyesi %0–100 arasındadır. Çıkış aygıtı listelenmiş numaradan seçilir;
varsayılan çıkış değiştirilir. Mevcut oynatma akışlarının anında yeni çıkışa
geçmesi uygulama/PipeWire davranışına bağlıdır. Mikrofon seviyesi %25 üst sınırı
korunur; çıkış komutları mikrofon seviyesine dokunmaz.

## Kontroller

119 birim testi: yönlendirme, rutin/alias döngüsü, iptal, sekme belirsizliği,
numaralı eski hedef, dosya sınırları, atomik üzerine yazmama, geri alma çakışması,
MPRIS belirsizliği, ses aygıtı seçimi ve kısayol basma/bırakma ayrımı.

`python -m tests.live_features`: yerel Firefox sekmeleri, hedef numaraları,
pencere büyütme/yerleştirme/küçültme ve geri alma; yerel Qt penceresinde numaralı
tıklama; gerçek ses çıkışı listesi.
`python -m tests.live_laya`: kurulu CPU Laya, %65 eşik, 61 hedef, onclick ve açık
Shadow DOM; tek eylem. API isteği veya indirme yapılmadı.

Gerçek müzik oynatıcısında parça değiştirme, çıkış sesi değiştirme ve KDE'nin
acil durdurma izin penceresi otomatik canlı testte uygulanmadı; adaptörleri birim
testleriyle sınandı. GPU modelinin bu sürümde ayrıca canlı testi yapılmadı.
