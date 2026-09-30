# Yerel İngilizce Laya

Ctrl+Alt+J açılışında `4` seçin. `3` veya boş giriş OpenCode Jev'i seçer.
Laya seçildikten sonra model yüklenir, yerel kontrol çalışır ve başarılıysa
Ctrl+Alt+V bas-konuş başlar. Laya anahtar istemez, OpenCode anahtarını okumaz.
Laya seçilince aygıt sorulur: `1` CPU, `2` NVIDIA GPU. CUDA destekli PyTorch
kurulu değilse GPU açık hata verir; CPU'ya sessiz geçiş yapılmaz. GPU bağımlılığı
kurulumu ayrı yapılır. Model ve sanal ortam Git deposuna dahil değildir;
yeni klonda hazır olduğu varsayılmaz.
Metin modu: `./desktop-agent --provider laya`.
Ses modu: `./desktop-agent listen --provider laya`.
Doğrudan aygıt seçimi: `./desktop-agent listen --provider laya --device cpu`
veya `--device cuda`.

Kurulum proje içindedir: `.local/laya/venv`, `.local/laya/model` ve
`.local/laya/install.json`. İngilizce checkpoint `convaiinnovations/laya`,
revision `55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851`; Laya 0.3.21 ve PyTorch CPU.
GPU için başka bir projenin sanal ortamı gerekmez. Kendi Laya ortamınızı kullanın;
CUDA kurulum yardımcısı `packaging/install-laya-gpu.sh` içindedir.
`LAYA_PYTHON` ile Laya kurulu Python yolunu, `LAYA_MODEL_DIR` ile indirilmiş model
klasörünü, isteğe bağlı `LAYA_GPU_PACKAGES` ile ayrı GPU paket klasörünü seçebilirsiniz.
Göreli yollar proje köküne göre çözülür, `~` kullanıcı ev dizinidir.

Örnek bağımsız kurulum (ağdan paket ve model indirir):

```sh
python3 -m venv .local/laya/venv
.local/laya/venv/bin/python -m pip install -r packaging/laya-requirements.lock
.local/laya/venv/bin/python -c "from huggingface_hub import snapshot_download; snapshot_download('convaiinnovations/laya', revision='55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851', local_dir='.local/laya/model')"
```

Python/PyTorch sürümleri platformunuzla uyumlu olmalıdır. GPU için CUDA destekli
PyTorch gerekir; desteklenmeyen platformlarda kurulumu ayrıca uyarlayın.
Bağımlılık sürümleri `packaging/laya-requirements.lock` içindedir. Diğer dil ve
typed-decisions modelleri indirilmedi. Ortam ana masaüstü Python'undan ayrıdır;
model yalnızca Laya seçilince ayrı işçi süreçte yüklenir, çıkışta süreç kapanır.
Çalışma sırasında Hugging Face offline modundadır; otomatik indirme yapılmaz.

Mevcut ses çözümleme, masaüstü/tarayıcı araçları ve onay kuralları korunur.
Yerel kararlar harici API'ye gönderilmez; ziyaret edilen web siteleri normal
ağ erişimini kullanır. Kesin uygulama/site/arama komutları modeli çağırmadan çalışır.

Laya'nın entropy temelli `confidence` değeri Jev ile aynı değildir. Bu adaptör
`answer_confidence` değerini kullanır; seçilen seçenek olasılığı ve bu değer için
Kullanıcı isteğiyle Laya seçim güveni ve seçenek olasılığı eşiği %65'tir
(`config/config.json`, `laya.threshold`). Jev eşikleri %80'dir. Bu, modelin bizim masaüstü görevlerimizde kalibre edildiği
anlamına gelmez. Model önce kısa bir soruyla operasyonu seçer, sonra yalnızca
o operasyonun hedef/metin sorularını yanıtlar. Büyük hedef kümeleri mevcut
checkpoint encoder'ıyla sıralanır; komutta adı geçen hedefler önceliklendirilir.
Model 12 adaylık listeyi değerlendirir; `none` seçeneği korunur. CLI kaç hedefin
kaç adaya indirildiğini gösterir. Güven bu daraltılmış listeye koşulludur;
tam ekran üzerinde kalibre edilmiş olasılık olarak yorumlanmamalıdır.
1.400 state tokenı aşılırsa veya seçenekler ayırt edilemezse açık hata verilir.
Çıktı sohbet değildir. Model ağırlıkları değiştirilmedi, fine-tuning yapılmadı.

Gerçek yerel yükleme, Noul bağlantı kontrolü ve basit tıklama seçimi doğrulandı.
Gerçek Firefox testindeki iki adımlı “Type hello world in Search and click Apply”
görevi %53 seçim güveniyle durdu; hiçbir eylem uygulanmadı. İngilizce temel modelin
bu görevde yeterli olmadığı görüldü; bu seçenek deneysel olarak sunulur.
Yeni giriş düzeninde aynı iki adımlı komutun ilk kararı %69,5 güvenle durdu;
bu görev hâlâ doğrulanmadı. Tek adımlı Click/Play komutu bir tıklamadan sonra durur,
aynı hedefe tekrar tekrar basılmaz. Gezinme KDE penceresi hazır olana kadar bekler
ve odağı doğrular; gözlem satırında aktif uygulama gösterilir.
Gerçek Laya + Firefox testinde 61 görünür kontrolden Shorts hedefi seçildi,
tam bir tıklama uygulandı ve sayfadaki etkisi doğrulandı (`tests/live_laya.py`).
119 otomatik test geçti. Bunlar tüm çok adımlı masaüstü görevlerinin doğruluğunu
kanıtlamaz; düşük güvenli seçim eylemden önce durdurulur.

2026-09-29.11: CPU/GPU için aynı yürütme sınırı kullanılır. Varsayılan komut
bir eylemden sonra durur; açık `and/then` ile belirtilen ek eylemler sayılır
(en fazla sekiz). Tırnak içindeki metin ek adım sayılmaz. Sınır dolunca tekrar
DONE kararı istenmez. Aynı eylem/hedef etiketi/payload aynı komutta yeniden
uygulanmaz; tekrar engeli ekran değişse de geçerlidir. İki yükleme beklemesi
sonrası durulur. Her eylem sonrası 350 ms ekran yerleşme süresi vardır. Bunlar
modelin yanlış hedef seçmesini tamamen önlemez; genel görev doğruluğu ayrıca
değerlendirilmelidir. Aynı işlemi bilinçli tekrarlamak için yeni komut verin.

Kaynaklar:
- https://github.com/NandhaKishorM/laya
- https://github.com/NandhaKishorM/laya/blob/main/laya/agent.py
