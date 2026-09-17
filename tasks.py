"""Bakım görevlerinin tanımları.

Her Task; arayüzde gösterilecek etiketi, çalıştırılacak bash komutunu,
root (pkexec) gerektirip gerektirmediğini ve (varsa) çalışması için
sistemde bulunması gereken bir komutu (ör. 'flatpak') tutar.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Task:
    id: str
    label: str
    command: str
    needs_root: bool = False
    requires_binary: Optional[str] = None


TASKS = [
    # ---------------- Paket Güncellemeleri ----------------
    Task(
        id="apt_update",
        label="APT paket listesini ve sistemi güncelle",
        command="apt update && apt upgrade -y",
        needs_root=True,
    ),
    Task(
        id="snap_refresh",
        label="Snap paketlerini güncelle",
        command="snap refresh",
        needs_root=True,
        requires_binary="snap",
    ),
    Task(
        id="flatpak_update",
        label="Flatpak paketlerini güncelle",
        command="flatpak update -y",
        needs_root=False,
        requires_binary="flatpak",
    ),
    # ---------------- Sistem Temizliği ----------------
    Task(
        id="apt_autoremove",
        label="Kullanılmayan (öksüz) paketleri kaldır",
        command="apt autoremove --purge -y",
        needs_root=True,
    ),
    Task(
        id="apt_clean",
        label="APT paket önbelleğini temizle",
        command="apt clean && apt autoclean",
        needs_root=True,
    ),
    Task(
        id="snap_cache_clean",
        label="Devre dışı Snap sürümlerini temizle",
        # 'snap list --all' çıktısında Notes sütununda 'disabled' geçen
        # (yani artık kullanılmayan eski) sürümleri tek tek kaldırır.
        command=(
            "snap list --all | awk '$6 ~ /disabled/ {print $1, $3}' | "
            "while read -r name revision; do "
            'snap remove "$name" --revision="$revision"; done'
        ),
        needs_root=True,
        requires_binary="snap",
    ),
    Task(
        id="flatpak_unused",
        label="Kullanılmayan Flatpak çalışma zamanlarını kaldır",
        command="flatpak uninstall --unused -y",
        needs_root=False,
        requires_binary="flatpak",
    ),
    Task(
        id="journal_vacuum",
        label="7 günden eski sistem günlüklerini temizle",
        command="journalctl --vacuum-time=7d",
        needs_root=True,
    ),
    Task(
        id="thumbnail_cache",
        label="Kullanıcı küçük resim (thumbnail) önbelleğini temizle",
        command='rm -rf "$HOME/.cache/thumbnails"/*',
        needs_root=False,
    ),
]
