# Ubuntu Bakım Aracı — Kullanım Kılavuzu ve Teknik Notlar

Bu dosya, uygulamanın nasıl kullanılacağını, hangi komutları çalıştırdığını ve
hangi kütüphanelerle nasıl yazıldığını tek yerde topluca açıklar.

---

## 1. Uygulama Ne Yapar?

Ubuntu üzerinde düzenli yapılan bakım işlerini (paket güncelleme + sistem
temizliği) tek bir pencereden, tek tıkla ve **tek parola isteğiyle** yapmayı
sağlayan bir GTK4/Libadwaita masaüstü uygulamasıdır.

---

## 2. Kurulum (bir kere yapılır)

```bash
sudo apt update
sudo apt install -y python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 policykit-1
```

Bu paketler ne işe yarar:

| Paket | Ne için gerekli |
|---|---|
| `python3-gi` | Python'dan GTK/GLib kütüphanelerine erişim (PyGObject) |
| `python3-gi-cairo` | GTK çizim (cairo) desteği |
| `gir1.2-gtk-4.0` | GTK 4 arayüz bileşenleri |
| `gir1.2-adw-1` | Libadwaita — modern GNOME/Ubuntu görünümü ve bileşenleri |
| `policykit-1` | `pkexec` komutu, root yetkisi isteyen grafik parola penceresi |

`pip install` gerekmez — hepsi Ubuntu'nun kendi paket deposundan, sistem
paketi olarak kurulur (PyGObject pip üzerinden değil apt üzerinden kurulmalı).

---

## 3. Nasıl Çalıştırılır?

```bash
cd ~/Masaüstü/ubuntu-bakim-araci
python3 main.py
```

Pencere açıldığında:

1. Üstte **"Tümünü Seç / Kaldır"** butonu ile tüm görevleri tek seferde
   işaretleyip kaldırabilirsin. Varsayılan olarak hepsi işaretlidir.
2. Listeden istemediğin görevlerin kutucuğunu tıklayıp kapatabilirsin.
   Alt yazıda "root yetkisi gerekir" ve/veya "'x' kurulu olmalı" notları
   hangi görevin ne gerektirdiğini gösterir.
3. Sağ üstteki **"Bakımı Başlat"** butonuna bas.
4. Seçtiğin görevler arasında root gerektiren biri varsa, sistem **bir kez**
   parola penceresi (pkexec) açar. Parolayı gir, geri kalan her şey otomatik
   ilerler.
5. Alt kısımdaki log alanında her komutun çıktısı gerçek zamanlı akar.
   Durum etiketi hangi görevin çalıştığını, ilerleme çubuğu ise genel
   ilerlemeyi gösterir.
6. İşlem sürerken **"Durdur"** butonuna basarsan, o an çalışan komut
   sonlandırılır ve kalan görevler iptal edilir (zaten tamamlanmış adımlar
   geri alınmaz).
7. Tüm görevler bitince durum etiketi "Bakım tamamlandı" olur, "Bakımı
   Başlat" butonu tekrar aktif hale gelir.

Uygulama menüsüne ekleme (isteğe bağlı) için ana [README.md](README.md)
dosyasındaki "Uygulama menüsüne ekleme" bölümüne bak.

---

## 4. Görevler ve Arka Planda Çalışan Komutlar

Görev tanımları [tasks.py](tasks.py) içinde. Her görev tek bir Python
nesnesi (`Task`) ile tanımlanır: etiket, komut, root gerekip gerekmediği ve
(varsa) hangi araç kurulu olmalı.

| # | Görev | Çalıştırılan komut | Root? | Gereken araç |
|---|---|---|---|---|
| 1 | APT paket listesini ve sistemi güncelle | `apt update && apt upgrade -y` | Evet | — |
| 2 | Snap paketlerini güncelle | `snap refresh` | Evet | `snap` |
| 3 | Flatpak paketlerini güncelle | `flatpak update -y` | Hayır | `flatpak` |
| 4 | Kullanılmayan (öksüz) paketleri kaldır | `apt autoremove --purge -y` | Evet | — |
| 5 | APT paket önbelleğini temizle | `apt clean && apt autoclean` | Evet | — |
| 6 | Devre dışı Snap sürümlerini temizle | `snap list --all` çıktısında "disabled" olan sürümleri bulup `snap remove --revision=...` ile tek tek siler | Evet | `snap` |
| 7 | Kullanılmayan Flatpak çalışma zamanlarını kaldır | `flatpak uninstall --unused -y` | Hayır | `flatpak` |
| 8 | 7 günden eski sistem günlüklerini temizle | `journalctl --vacuum-time=7d` | Evet | — |
| 9 | Kullanıcı thumbnail önbelleğini temizle | `rm -rf "$HOME/.cache/thumbnails"/*` | Hayır | — |
| 10 | Çöp kutusunu boşalt | `~/.local/share/Trash/{files,info}` klasörlerini silip boş olarak yeniden oluşturur | Hayır | — |

**Sistemde kurulu olmayan araç** (ör. flatpak yoksa) gerektiren bir görev,
otomatik atlanır ve log alanına `[Atlandı] ...` notu düşülür — hata vermez.

**Neden Flatpak görevleri root istemiyor?** Sistem geneli Flatpak
kurulumlarında gerekirse Flatpak kendi PolicyKit penceresini zaten kendisi
açar; uygulamanın ayrıca pkexec ile sarmasına gerek yok.

---

## 5. Root Yetkisi Nasıl Alınıyor? (`pkexec` akışı)

Her root gerektiren görev için ayrı ayrı parola sormak yerine:

1. Kullanıcı "Bakımı Başlat" dediğinde, seçilen root gerektiren görevler
   ayıklanır.
2. Bunların komutları, aralarına durum satırları (`echo "###STEP### ..."`)
   eklenerek **tek bir bash betiğinde** birleştirilir.
3. Betik, `tempfile.mkstemp()` ile geçici bir dosyaya yazılır, `chmod 700`
   ile sadece kullanıcının okuyup çalıştırabileceği hale getirilir.
4. Bu betik `pkexec bash /tmp/....sh` şeklinde **tek bir komut** olarak
   çalıştırılır → PolicyKit **bir kez** parola sorar, betik tamamen root
   olarak baştan sona çalışır.
5. Betik bittiğinde geçici dosya otomatik silinir.

Ekstra önlem: `apt upgrade` sırasında bazı sistemlerde `needrestart` aracı
"şu servisleri yeniden başlatayım mı?" diye interaktif bir pencere/prompt
açabilir; grafik arayüzden çalıştığı için bu prompt'u cevaplayacak bir
terminal olmadığından betik burada asılı kalabilir. Bunu önlemek için betiğin
başına şunlar eklenir:

```bash
export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_MODE=a
```

Parola hiçbir zaman uygulama tarafından okunmaz, saklanmaz ya da işlenmez —
tamamen PolicyKit'in kendi (sistem) parola penceresi üzerinden alınır.

---

## 6. Kullanılan Kütüphaneler / Modüller

### Arayüz (GTK4 / Libadwaita — PyGObject üzerinden)

| Modül | Nereden | Ne için kullanıldı |
|---|---|---|
| `gi` | sistem paketi (`python3-gi`) | Python ↔ GObject introspection köprüsü; `gi.require_version` ile GTK4/Adw sürümü sabitlenir |
| `gi.repository.Gtk` | `gir1.2-gtk-4.0` | Pencere içi bileşenler: `Button`, `Box`, `Label`, `CheckButton`, `ProgressBar`, `TextView`, `TextBuffer`, `ScrolledWindow` |
| `gi.repository.Adw` | `gir1.2-adw-1` | Libadwaita bileşenleri: `Application`, `ApplicationWindow`, `HeaderBar`, `ToolbarView`, `PreferencesGroup`, `ActionRow` — Ubuntu/GNOME'un modern, native görünümünü verir |
| `gi.repository.GLib` | `gir1.2-gtk-4.0` ile gelir | `GLib.idle_add` — arka plan thread'inden ana (UI) thread'ine **güvenli** şekilde mesaj/güncelleme geçirmek için |

### Python standart kütüphanesi (ekstra kurulum gerekmez)

| Modül | Ne için kullanıldı |
|---|---|
| `dataclasses` | `Task` veri sınıfını (etiket, komut, root gereksinimi) tanımlamak için |
| `typing` | `Optional[str]` tip belirtimi için |
| `subprocess` | Komutları (`apt`, `snap`, `flatpak`, `pkexec` betiği vb.) çalıştırıp çıktısını okumak için (`Popen`) |
| `threading` | Komutları arayüzü kilitlemeden arka planda çalıştırmak için (`Thread`, `Event`) |
| `tempfile` | Root betiği için geçici, güvenli bir dosya oluşturmak için (`mkstemp`) |
| `os` | Geçici dosyanın izinlerini ayarlamak (`chmod`) ve iş bitince silmek (`remove`) için |
| `shutil` | Bir komutun (ör. `flatpak`) sistemde kurulu olup olmadığını kontrol etmek için (`which`) |
| `shlex` | Geçici betik dosyasının yolunu shell komutuna güvenli şekilde eklemek için (`quote`) |

### Uygulamanın çağırdığı sistem araçları (Python kütüphanesi değil, harici komutlar)

`apt`, `snap`, `flatpak`, `journalctl`, `pkexec`, `bash`, `awk`, `rm` —
bunların hepsi Ubuntu'da zaten hazır gelir, ayrı kurulum gerekmez (flatpak
hariç; o kuruluysa ilgili görevler çalışır, değilse otomatik atlanır).

---

## 7. Dosya Yapısı

```
ubuntu-bakim-araci/
├── main.py                       # Uygulamanın giriş noktası, pencere ve arayüz mantığı
├── tasks.py                      # Görev tanımları (etiket, komut, root gereksinimi)
├── runner.py                     # Komutları arka plan thread'inde çalıştıran motor
├── ubuntu-bakim-araci.desktop    # Uygulama menüsü kısayolu şablonu
├── icon.svg                      # Uygulama simgesi (dişli + onay rozeti)
├── README.md                     # Kurulum ve hızlı başlangıç
└── KULLANIM_KILAVUZU.md          # Bu dosya — ayrıntılı kullanım ve teknik notlar
```

**Kod neden bu üç dosyaya bölündü?**
Her dosyanın tek bir sorumluluğu var, bu da kodu kısa ve okunması kolay
tutuyor:

- `tasks.py` — sadece **veri**: hangi görev, hangi komutu çalıştırıyor.
  Yeni bir bakım görevi eklemek istersen sadece bu dosyaya bir `Task(...)`
  satırı eklemen yeterli, arayüze veya çalıştırma mantığına dokunmana gerek
  yok.
- `runner.py` — sadece **çalıştırma**: bir komut listesini sırayla çalıştırıp
  çıktısını arayüze iletir. GTK'dan tamamen habersizdir, tek bildiği
  `GLib.idle_add` ile arayüze güvenli haber vermek.
- `main.py` — sadece **arayüz**: pencereyi kurar, kullanıcı etkileşimlerini
  (tıklama, seçim) dinler, `runner.py`'a iş verir ve gelen sonuçları ekrana
  yansıtır.

---

## 8. Arayüz Akışı Özeti (kod içinde nerede)

- `_build_ui()` → pencereyi ve tüm bileşenleri oluşturur.
- `_on_run_clicked()` → seçili görevleri toplar, kurulu olmayan araçları
  eler, root/kullanıcı görevlerini ayırır, `TaskRunner.run()`'ı çağırır.
- `_build_root_batch_task()` → root gerektiren görevleri tek betikte
  birleştirip tek `pkexec` komutuna dönüştürür.
- `TaskRunner._run_all()` (runner.py) → görevleri sırayla çalıştırır, her
  adımda `GLib.idle_add` ile `main.py`'daki `_on_task_start` /
  `_on_output` / `_on_task_done` fonksiyonlarını tetikler.
- `_on_all_done()` → ilerleme çubuğunu tamamlar, butonları eski haline
  getirir, geçici betik dosyasını siler.

---

## 9. Sorun Giderme

| Belirti | Olası sebep / çözüm |
|---|---|
| Pencere hiç açılmıyor, terminalde `ModuleNotFoundError: No module named 'gi'` | Bölüm 2'deki apt paketleri kurulmamış |
| `pkexec` parola penceresi çıkmıyor, hata veriyor | `policykit-1` kurulu değil veya masaüstü ortamında bir PolicyKit auth agent (GNOME'da varsayılan gelir) çalışmıyor olabilir |
| Bakım "Root gerektiren işlemler" adımında uzun süre takılı kalıyor | `apt upgrade` sırasında `needrestart` interaktif prompt açmış olabilir; betikte `NEEDRESTART_MODE=a` zaten ayarlı, yine de olursa "Durdur"a basıp tekrar deneyin |
| Bir görev "[Atlandı] ... bulunamadı" diyor | Görevin gerektirdiği araç (ör. `flatpak`) sistemde kurulu değil, sorun değil — kurulmak istenirse ayrıca kurulmalı |
