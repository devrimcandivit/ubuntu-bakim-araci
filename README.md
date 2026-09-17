# Ubuntu Bakım Aracı

APT, Snap ve Flatpak güncellemelerini ve sistem temizliği görevlerini (öksüz paketler,
önbellekler, eski sistem günlükleri, thumbnail önbelleği) tek bir GTK4 / Libadwaita
penceresinden yürüten basit bir masaüstü bakım uygulaması.

## Özellikler

- Her görev ayrı ayrı işaretlenip kapatılabilir, "Tümünü Seç / Kaldır" ile toplu seçim yapılabilir.
- Root (yönetici) yetkisi gerektiren görevler (`apt`, sistem geneli `snap`, `journalctl`)
  çalıştırma anında tek bir bash betiğinde birleştirilir ve **tek bir `pkexec` parola
  istemi** ile çalıştırılır — her adım için ayrı ayrı parola sorulmaz.
- Root gerektirmeyen görevler (`flatpak`, thumbnail önbelleği) doğrudan kullanıcı
  yetkisiyle çalışır; `flatpak`'in kendi sistem güncellemeleri gerektiğinde zaten
  kendi PolicyKit isteğini açar.
- Sistemde kurulu olmayan bir araç (ör. `flatpak` yoksa) gerektiren görevler otomatik
  olarak atlanır ve log'a not düşülür.
- Komut çıktısı gerçek zamanlı olarak log alanında gösterilir, arayüz komutlar
  çalışırken kilitlenmez (arka plan thread'i kullanılır).
- İlerleme çubuğu ve durum etiketi hangi görevin o an çalıştığını gösterir.
- "Durdur" butonu, o an çalışan komutu sonlandırıp kalan görevleri iptal eder.

## Gereksinimler ve Kurulum (Ubuntu)

Aşağıdaki sistem paketlerini kurun (pip gerekmez, PyGObject sistem paketi olarak gelir):

```bash
sudo apt update
sudo apt install -y python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 policykit-1
```

> Not: `gir1.2-adw-1` (Libadwaita GObject introspection) Ubuntu 22.04 ve üzerinde
> mevcuttur. Daha eski sürümlerde bulunmayabilir.

## Çalıştırma

```bash
cd ~/Masaüstü/ubuntu-bakim-araci
python3 main.py
```

Root gerektiren görevleri seçip "Bakımı Başlat" dediğinizde, sistem bir kez
grafik parola penceresi (`pkexec`) gösterecektir. Bu, apt/snap/journalctl
işlemlerinin tamamı için yeterlidir.

## Uygulama menüsüne ekleme (.desktop dosyası)

Proje klasöründe hazır bir `ubuntu-bakim-araci.desktop` şablonu bulunuyor.
Kurulum yolunu gerçek dizine göre ayarlayıp kullanıcı uygulama dizinine
kopyalamak için:

```bash
APP_DIR="$HOME/Masaüstü/ubuntu-bakim-araci"
mkdir -p ~/.local/share/applications
sed "s|__APP_DIR__|$APP_DIR|g" "$APP_DIR/ubuntu-bakim-araci.desktop" \
  > ~/.local/share/applications/ubuntu-bakim-araci.desktop
update-desktop-database ~/.local/share/applications 2>/dev/null || true
```

Bu işlemden sonra uygulama, Ubuntu uygulama menüsünde **"Ubuntu Bakım Aracı"**
adıyla görünüp doğrudan başlatılabilir.

## Dosyalar

| Dosya | Açıklama |
|---|---|
| `main.py` | GTK4/Libadwaita arayüzü, ana uygulama giriş noktası |
| `tasks.py` | Bakım görevlerinin tanımları (etiket, komut, root gerekliliği) |
| `runner.py` | Görevleri arka plan thread'inde çalıştırıp arayüze aktaran modül |
| `ubuntu-bakim-araci.desktop` | Uygulama menüsü kısayolu şablonu |

## Güvenlik notları

- Root yetkisi yalnızca `pkexec` üzerinden, PolicyKit'in kendi kimlik doğrulama
  penceresiyle alınır; parola uygulama içinde hiçbir şekilde saklanmaz veya işlenmez.
- Root betiği her çalıştırmada geçici bir dosyaya (`mkstemp`, mod `0700`) yazılır ve
  iş bittiğinde otomatik olarak silinir.
- `apt upgrade` sırasında olası interaktif servis yeniden başlatma sorularının
  (`needrestart`) betiği kilitlememesi için `DEBIAN_FRONTEND=noninteractive` ve
  `NEEDRESTART_MODE=a` ortam değişkenleri betik içinde ayarlanır.
