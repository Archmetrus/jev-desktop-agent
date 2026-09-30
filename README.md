# Jev masaüstü ajanı

İngilizce ses/metin komutu → Jev'in güncel eylem ve hedef seçimi → masaüstünde uygulama → yeniden gözlem.
Jev sohbet cevabı veya sesli cevap üretmez. CLI söylediklerinizi, seçilen eylemi ve yürütme sonucunu gösterir.
Qwen/Ollama veya ikinci bir metin modeli kullanılmaz.

Yeni sürümde [11 ek yetenek](docs/features.md) bulunur: medya, sekmeler, rutinler,
öğretilen komutlar, dosyalar, pencereler, numaralı hedefler, geçmiş/geri alma,
Qt paneli, durdurma ve çıkış sesi. `/features` listeyi, `/panel` kontrol panelini açar.
Türkçe desteği kullanıcı isteğiyle ertelendi. [Uygulama planı](docs/capability-plan.md).

## Çalıştırma sınırları

- **Masaüstü kontrolü Linux, KDE ve Wayland ortamı gerektirir.** Windows/macOS bu sürümde desteklenmez.
- Ses modu için whisper.cpp, İngilizce ses modeli ve sistem ses araçları ayrıca kurulmalıdır. `.local/` içindeki araçlar, model dosyaları ve sanal ortamlar depoya dahil değildir.
- İsteğe bağlı Laya sağlayıcısı ayrı Python ortamı ve indirilmiş model gerektirir. GPU modu için uyumlu NVIDIA/CUDA ve CUDA destekli PyTorch gerekir; kullanılamazsa otomatik olarak CPU'ya geçmez.
- Kurulum ayrıntıları [Yeni bilgisayarda gereksinimler](#yeni-bilgisayarda-gereksinimler) ve [Laya rehberinde](docs/laya.md) bulunur. Birim testleri ve yol kontrolleri, her masaüstü görevinin başarılı olacağını garanti etmez.

## Kullanım

```sh
cd "$(git rev-parse --show-toplevel)"
./desktop-agent listen
```

OpenCode Zen API anahtarını terminaldeki gizli girişe yazın; OpenRouter anahtarı
bu sağlayıcıda kullanılamaz. Doğrulanan Zen anahtarı KDE Secret Service/KWallet
kasasında saklanır ve sonraki açılışta alınır; kaynak veya düz metin dosyaya yazılmaz.
Kasa kullanılamazsa yalnızca mevcut oturumda tutulur. **Ctrl+Alt+J seçim menüsünü açar:**
`3` OpenCode Jev (varsayılan), `4` Laya İngilizce yerel. Laya API anahtarı istemez.
Seçim ve model testi başarılı olunca bas-konuş başlar.
KDE kısayol iznini onaylayın. **Ctrl+Alt+V basılıyken konuşun, bırakınca komut uygulanır.**
Beklemede ve eylem sırasında mikrofon kapalıdır. Mikrofon seviyesi %25'in üstündeyse
indirilir; daha düşük seviyeye dokunulmaz. Kayıt en fazla 20 saniyedir.
Gösterge bekleme/kayıt/çözümleme/eylem durumunu gösterir, odak almaz.
Yerel Whisper ve mevcut FFmpeg filtresi kullanılır; çevre konuşmasını güvenilir biçimde ayırmaz.

Metinle kullanmak için `./desktop-agent` çalıştırın. Varsayılan sağlayıcı OpenCode Zen,
model `jev-1.13-free` olur. Anahtar gizli girildikten sonra gerçek API bağlantısı otomatik
sınanır. Başarısızsa başlangıçta sesli dinleme başlatılmaz; `/key` ile anahtarı değiştirip
`/check` ile tekrar sınayabilirsiniz. Bağlantı testi masaüstü eylemi yapmaz.
Typesafe isteğe bağlı `--provider typesafe` ile seçilir. Önceki ücretsiz model/OpenRouter
eşleştirmesi geçersizdir ve ağ çağrısından önce durdurulur. Ücretli modele otomatik dönüş yoktur.

Örnek komutlar:

- `Open browser`
- `Open Google Chrome`
- `Go to youtube.com`
- `Search YouTube for Interstellar soundtrack`
- `Type "hello world" in Search and click Search`
- `Select Two in Category`
- `Scroll down`
- `Press Tab`
- `Focus Dolphin`

Yazılacak metin komuttan alınır; Jev yeni metin üretmez. Sesli komutlarda “search … for …”
ve “type …” ifadeleri metin adaylarını oluşturur. Komutları açık hedef isimleriyle vermek seçimi kolaylaştırır.

CLI komutları: `/tools` yetenekler, `/windows` açık pencereler, `/observe` güncel hedefler,
`/apps` uygulamalar, `/key` anahtar değiştirme, `/forget-key` kasadaki anahtarı silme,
`/listen` bas-konuş, `/help` yardım, `/quit` çıkış. `/forget-key` mevcut oturum anahtarını
etkilemez; sonraki açılışta yeniden giriş gerekir.
Ctrl+C dinlemeyi bitirip metin istemine döner. Alternatif `/listen ptt`, `/listen wake`,
`/listen continuous` modları korunur; gürültülü ortamda varsayılan `hold` kullanılır.

## Eylemler ve sınırlar

Uygulama açma/öne getirme, URL ve arama açma, görünür düğmeye tıklama, alana yazma,
açılır listeden seçim, desteklenen klavye kısayolları ve kaydırma uygulanır.
Her adım güncel hedefleri yeniden okur; eski veya örtülmüş hedefler kullanılmaz.
Döngü en fazla 20 adım, 90 saniye ve üç ilerlemesiz adımla sınırlandırılır.

Masaüstünde KDE/KWin ve AT-SPI kullanılır. Erişilebilirlik hedefi sunmayan uygulamaların
kontrolleri kullanılamaz. Tarayıcı gezintisi mevcut Firefox ile ayrı görev profili açar;
DOM hedeflerini yerel Marionette bağlantısından okur. Mevcut Firefox profilinizi kullanmaz.
Görev tarayıcısı çıkışta incelemeniz için açık bırakılır; profilleri `.state/browsers/` altındadır.
Tarayıcıyı kapattığınızda sonraki gezinme isteği eski bağlantıyı temizleyip yeni oturum açar.
Klavye/fare kontrolü gerektiğinde KDE'nin ayrı RemoteDesktop izin penceresi açılabilir.

Kesin uygulama adları/takma adları ve tek site/arama komutları yapılandırmadan
doğrudan çözülür; bunlar için API çağrısı yapılmaz. Belirsiz veya çok adımlı
görevlerde Jev yalnızca kodun oluşturduğu kapalı seçeneklerden seçim yapar. Shell, JavaScript,
koordinat veya serbest yazı üretemez. Terminal içine tıklama/yazma engellenir.
Parola ve API anahtarı alanları hedef listesinden çıkarılır; hassas komutlar API'ye gönderilmez.
Genel görevlerde komut ve gözlenen arayüz metinleri seçilen sağlayıcıya gönderilir.
Silme/gönderme/satın alma gibi hassas işlemler ve Enter/Save terminalde `evet` onayı ister.
Tek komut modunda onay gerektiren işlemler uygulanmaz.

CLI eylem etkisinin doğrulanıp doğrulanmadığını gösterir. `ACTIONS_FINISHED`, Jev'in döngüyü
bitirdiğini belirtir; genel görevin tamamının bağımsız doğrulandığı anlamına gelmez
(`goal_verified: false`). Sonucu ekrandan kontrol edin. Uygulama açma yolunda pencere
ve odağı ayrıca doğrulanır. Başarısız seçimler hata koduyla görünür, sohbet cevabı verilmez.

## Kurulum ve kontroller

Geliştirme ortamında whisper.cpp v1.9.4 ve İngilizce base.en modeli kullanıldı.
Yeni klonda `.local/` ses araçları ve model bulunmaz; aşağıdaki gereksinimleri hazırlayın. Eksik paket/model otomatik indirilmez.
Sistem Python'u, GI/dbus, PySide6, PipeWire, FFmpeg ve Firefox kullanılır. KDE/Wayland gerekir.

```sh
./desktop-agent speech-status
./desktop-agent tools
./desktop-agent text 'Search YouTube for Interstellar soundtrack' --dry-run
python -m unittest discover -s tests -q
```

`--dry-run` ağ veya masaüstü eylemi yapmaz; yalnızca aday üretimini kontrol eder.
Genel görevlerin tek komut modunda sağlayıcıya göre `OPENCODE_API_KEY`,
`OPENROUTER_API_KEY` veya `TYPESAFE_API_KEY` gerekir. Kesin yapılandırılmış komutlar anahtarsız çalışır. Anahtarı komut argümanına veya kaynak dosyaya yazmayın.

119 otomatik test geçti. Gerçek KDE testinde AT-SPI alanına yazma/düğmeye basma ve
portal üzerinden Ctrl+T doğrulandı. Gerçek Firefox testinde gezinme, yazma, tıklama,
liste seçimi, kaydırma ve eski hedef reddi doğrulandı. Bu çok adımlı entegrasyon testi
çevrimdışı seçim politikası kullanır; genel görevlerin gerçek Jev seçimiyle doğrulanması
ayrı kullanıcı denemesidir. `Open browser`, `Open Chrome`, `Open YouTube` ve
`Search YouTube for Interstellar Soundtrack` gerçek KDE/Firefox üzerinde API
anahtarı olmadan doğrudan yürütülerek doğrulandı. Kullanıcı gerçek ses → OpenRouter/Jev → tarayıcı açma yolunu doğruladı.

`LOW_CONFIDENCE`: seçim güveni düşük. `TASK_BLOCKED`: kullanılabilir eylem/hedef yok.
`NO_PROGRESS`: ekran ilerlemiyor. `CONFIRMATION_REQUIRED`: onay gerekiyor.
`AUTHENTICATION_FAILED`: anahtar reddedildi. `INSUFFICIENT_CREDITS`: kredi yetersiz.
Diğer HTTP hataları kodla gösterilir; anahtar ve ham hata yanıtı loglanmaz.

[Yöntemler ve incelenen kaynaklar](docs/approaches.md).

Genel görevlerde ilk URL/arama adımı diğer ekran kontrollerinden ayrılır. Bilinen bir
siteye arama komutu o sitenin arama adresini sunar; ana sayfa ve başka sitenin
araması eklenmez. Tamamlanan gezinme tekrarlanmaz. `LOW_CONFIDENCE` durumunda
CLI hangi sorunun, seçimin, güvenin ve olasılığın reddedildiğini gösterir. Eşikler
Jev için %80'dir; Laya için kullanıcı isteğiyle %65'tir. Chrome sistemde mevcut olduğundan uygulama listesine eklendi;
genel DOM otomasyonu görev Firefox profilinde çalışmaya devam eder.

Sürüm 2026-09-29.3: Genel görevlerin operasyon sorusu artık gerçek URL adaylarını
ve gezinme aracının Firefox’u kendisinin açabildiğini içerir. Başka bir soru
başlığının model tarafından otomatik görüldüğü varsayılmaz. Gezinme doğrulaması
yalnızca HTTP adresi görülmesine değil, istenen host/yol/arama parametrelerine bakar;
başka adrese yönlendirme görev başarısı sayılmaz.

`jev-1.13-free` OpenCode Zen belgesinde doğrulandı; OpenRouter modeli değildir.
Gerçek OpenCode API kabulü ücretsiz erişimle doğrulandı. Ücretli modele otomatik dönüş yapılmaz. Model denemesi
için doğrudan komut yoluna girmeyen `Search YouTube for jazz and scroll down`
gibi çok adımlı bir görev kullanın.

Ücretsiz modelin doğru sağlayıcısı OpenCode Zen’dir: `--provider opencode`,
`OPENCODE_API_KEY`, `https://opencode.ai/zen/v1/systemone`.
[Resmî Jev açıklaması](https://opencode.ai/docs/zen/#jev).
OpenRouter altında `jev-1.13-free` seçimi artık ağ çağrısından önce
`PROVIDER_MODEL_MISMATCH` ile durur. OpenRouter anahtarı başka sağlayıcıya
aktarılmaz; ücretli model veya başka sağlayıcıya otomatik geçiş yapılmaz.

[OpenCode Zen entegrasyonu ve gerçek API testi](docs/opencode.md):
`./desktop-agent --provider opencode` ile gizli anahtarı girip `/check` çalıştırın.
Bu kontrol gerçek API isteği yapar, masaüstü eylemi yapmaz. Sonrasında `/listen`
ile sesli kullanıma geçin.

Sürüm 2026-09-29.4: Gerçek API bağlantısı, uygulamayı tanıtan User-Agent ile
ücretsiz OpenCode Jev uç noktasında doğrulandı. Varsayılan Python istemcisi
Cloudflare 1010 ile reddediliyordu. Özel kullanıcı anahtarının geçerliliği
kendi oturumunda `/check` ile doğrulanmalıdır. Genel görevlerin tümü için
başarı garantisi veya tamamlanmış gerçek Jev görev testi iddiası yoktur.

Sürüm 2026-09-29.5: `config/config.json` varsayılan sağlayıcısı `opencode` oldu.
Hem metin hem bas-konuş başlangıcı aynı ücretsiz modeli kullanır. Yeni anahtar
girişinden sonra bağlantı otomatik sınanır.

Sürüm 2026-09-29.6: Kapanan görev Firefox'una yeniden bağlanma düzeltildi.
Ctrl+Alt+J başlatma kısayolu kuruldu; Ctrl+Alt+V bas-konuş kısayolu korunur.
Doğrulanmış Zen anahtarı güvenli kasada hatırlanır. Oturum kapanınca bellekteki
anahtar temizlenir; kasa kaydı `/forget-key` ile silinene kadar kalır.

Sürüm 2026-09-29.7: [Yerel İngilizce Laya](docs/laya.md) ayrı bir seçenek olarak
kuruldu. Ctrl+Alt+J sağlayıcıyı sorar; `4` Laya, `3` OpenCode Jev'dir. Laya API
anahtarı gerektirmez ve yalnızca seçildiğinde yüklenir. Kurulum `.local/laya/`
altındadır; çalışma sırasında model indirilmez. Yerel modelin hedef/context
sınırları ve güven ölçeği ayrı ele alınır. Search alan adı web arama komutuyla
karıştırılmaz.

Sürüm 2026-09-29.8: Laya operasyon ve hedef seçimini ayrı kısa sorularla yapar.
Büyük hedef listeleri mevcut encoder ile 12 adaya daraltılır; sabit 20 hedef
engeli kaldırıldı. Güven daraltılmış listeye koşulludur; eşikler düşürülmedi.
Tek Click/Play isteği bir tıklamadan sonra durur. Tarayıcı gezinmesi KWin
penceresinin hazır olmasını bekler ve odaklamayı doğrular. Gözlem aktif uygulamayı
da gösterir. Model eğitimi ve masaüstü kalibrasyonu yapılmadı.

Sürüm 2026-09-29.9: Laya eşiği %65; açılışta CPU/GPU seçimi sorulur. GPU için
CUDA destekli PyTorch gerekir; bağımlılıklar kullanıcı onayı olmadan indirilmez.
DOM taraması açık Shadow DOM ve onclick kontrollerini kapsar, 300 görünür hedefe
kadar okuyabilir. Rastgele DOM kimlikleri modele verilmez; sabit aday adları kod
içinde gerçek hedefe eşlenir. Kapalı Shadow DOM ve iframe içleri bu adaptörde
desteklenmez; native erişilebilirlik ve mevcut Firefox hedeflerine bağlıdır.

Sürüm 2026-09-29.10: Tetris ortamındaki kurulu GPU PyTorch/CUDA paketleri
`.local/laya/gpu-packages` bağlantıları üzerinden yeniden kullanılır. GPU
çalışması için yeni indirme/kopyalama yapılmadı; CPU ortamı korunur. Kaynak
Tetris ortamı silinirse GPU bağlantısı çalışmaz. Açılışta `4 → 2` GPU seçer.

Sürüm 2026-09-29.11: Laya tek eylemli komuttan sonra yeni karar istemeden durur.
Açık çok adımlı komutların eylem sayısı sınırlanır; aynı eylemin aynı komutta
tekrarı ekran değişse bile engellenir. CPU/GPU aynı sınırları kullanır;
eylemden sonra 350 ms ekran yerleşme beklemesi eklenmiştir. Eşik %65 olarak kalır.

Sürüm 2026-09-29.12: 11 yetenek genişletmesi eklendi. Tanımlı komutlar model/API
çağrısı yapmadan çalışır. Dosya taşıma atomik ve üzerine yazmadan uygulanır.
Geri alma çakışmayı denetler. Bas-konuşta Ctrl+Alt+X, panelde Durdur kullanılır;
iptal edilen model yanıtı sonraki masaüstü adımına dönüşmez.

## Proje dizini

Depoyu istediğiniz klasöre klonlayıp o dizine girin. `git rev-parse --show-toplevel` kullanılan komutlar klonun içinden çalıştırılır; kullanıcı adı veya sabit bir ana dizin gerekmez.

## Linux masaüstü kısayolu

Kısayolu `python3 packaging/install-desktop.py` ile kurun. Kurucu proje konumunu çözüp `$XDG_DATA_HOME/applications` (varsayılan `~/.local/share/applications`) içine yazar. `.desktop` dosyası şablondur; doğrudan kopyalamayın. Projeyi taşırsanız kurucuyu yeniden çalıştırın.

## Yeni bilgisayarda gereksinimler

Bu masaüstü ajanı Linux/KDE ortamı içindir. Python, PyGObject/GTK AT-SPI, Qt, DBus/Secret Service, Konsole, FFmpeg ve kullanılan masaüstü araçlarını dağıtımınızın paket yöneticisiyle kurun. Desteklenen uygulama komutlarını `config/apps.json` içinde bilgisayarınıza göre ayarlayın.

`.local` içindeki modeller ve sanal ortamlar depoya dahil değildir. Ses modu için `config/config.json` içindeki `speech.binary` ve `speech.model` yollarına whisper.cpp çalıştırılabilir dosyası ve İngilizce model yerleştirin; göreli yollar proje köküne göre çözülür. İsteğe bağlı Laya kurulumu [docs/laya.md](docs/laya.md) içindedir. Windows/macOS masaüstü kontrolü bu sürümde desteklenmez.
