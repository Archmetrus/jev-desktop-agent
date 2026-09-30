# Yetenek genişletme planı

Kullanıcı sırası korunur. Yeni komutlar önce kodun tanımlı işlem katmanına gider;
modelden serbest metin, kabuk komutu veya koordinat üretilmez. İndirme yapılmaz.

1. [x] MPRIS müzik/video: oynat, duraklat, sonraki/önceki.
2. [x] Görev Firefox sekmeleri: listele, aç, kapat, başlığa göre geç.
3. [x] Adlandırılmış rutinler: kullanıcı tanımlar; en fazla 8 adım, iç içe rutin yok.
4. [x] Öğretilen komutlar: açık eşleme, kalıcı yerel kayıt, döngü engeli.
5. [x] Dosyalar: aç, ara, klasör oluştur, taşı/yeniden adlandır; çöp için onay.
6. [x] Pencereler: büyüt/küçült, sağ/sol yerleştir, sanal masaüstüne taşı.
7. [x] Numaralı hedefler: ekranda/terminalde göster, güncel hedefe tıkla.
8. [x] Yerel eylem geçmişi; güvenli ters işlemi olan adımlar için geri al.
9. [-] Türkçe: kullanıcının son talebiyle ertelendi; model indirilmeyecek.
10. [x] Küçük Qt paneli: sağlayıcı/CPU/GPU seçimi, durum/geçmiş, durdur.
11. [x] Acil durdurma: Ctrl+Alt+X (bas-konuş dinlemesinde); bekleyen adımları iptal et.
12. [x] Ses: çıkış seviyesi, sessiz, çıkış aygıtı seçimi.

## Doğrulama

İşlem yönlendirme, belirsiz hedef, eski hedef, dosya sınırları, rutin döngüsü,
iptal ve geri alma çakışmaları birim testleriyle kontrol edilir. Mevcut testler
korunur. Gerçek masaüstü işlemleri yalnızca yerel test penceresi/dosyalarıyla
sınanır. Test edilmemiş canlı senaryolar tamamlandı diye raporlanmaz.

## Türkçe araştırması

Kurulu Whisper `base.en` İngilizce içindir; çok dilli Whisper Türkçeyi destekler:
https://github.com/ggml-org/whisper.cpp
Laya çok dilli benchmarkında Türkçe MASSIVE 20 seçenekli niyet testi yaklaşık
%37 doğruluk; bu sonuç masaüstü görevlerinin güvenilirliği anlamına gelmez:
https://github.com/NandhaKishorM/laya/blob/main/BENCHMARKS.md
Türkçe ses/metin geliştirmesi bu sürüm kapsamından çıkarılmıştır.

## Sonuç

11 aşama kodlandı; 9. aşama ertelendi. Kullanım ve sınırlar: [features.md](features.md).
119 birim testi ve gerçek yerel Firefox/KDE entegrasyon kontrolleri geçti.
Yerel CPU Laya testi de geçti. Yeni indirme yapılmadı.

Panel: KDE'nin yerel açık/gri paleti, sistem yazı tipi, 24 px Jev başlığı;
komut ve eylem alanları soldan hizalı. Sağlayıcı/aygıt üst sırada; Durdur aynı
satırda sürekli görünür, kırmızı metin (#b42318). Hedef işaretleri mavi (#164b87).
