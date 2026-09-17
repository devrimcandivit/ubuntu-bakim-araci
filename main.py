#!/usr/bin/env python3
"""Ubuntu Bakım Aracı.

APT / Snap / Flatpak güncellemelerini ve sistem temizliği görevlerini
tek bir GTK4 + Libadwaita pencereden yürüten basit bir bakım uygulaması.

Root gerektiren görevler (apt, snap sistem komutları, journalctl vb.)
tek bir bash betiğinde birleştirilip 'pkexec' ile bir kerede çalıştırılır;
böylece kullanıcıya görev başına değil, oturum başına bir kez parola sorulur.
"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

import os
import shlex
import shutil
import tempfile

from tasks import TASKS, Task
from runner import TaskRunner

STEP_MARKER = "###STEP### "


class MaintenanceWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Ubuntu Bakım Aracı")
        self.set_default_size(760, 660)

        self.runner = TaskRunner(
            on_output=self._on_output,
            on_task_start=self._on_task_start,
            on_task_done=self._on_task_done,
            on_all_done=self._on_all_done,
        )

        self._checkbuttons = {}
        self._temp_script_path = None
        self._queue_total = 0
        self._queue_done = 0

        self._build_ui()

    # ------------------------------------------------------------------
    # UI kurulumu
    # ------------------------------------------------------------------
    def _build_ui(self):
        toolbar_view = Adw.ToolbarView()

        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        self.select_all_button = Gtk.Button(label="Tümünü Seç / Kaldır")
        self.select_all_button.connect("clicked", self._on_select_all_clicked)
        header.pack_start(self.select_all_button)

        self.stop_button = Gtk.Button(label="Durdur")
        self.stop_button.set_sensitive(False)
        self.stop_button.connect("clicked", self._on_stop_clicked)
        header.pack_end(self.stop_button)

        self.run_button = Gtk.Button(label="Bakımı Başlat")
        self.run_button.add_css_class("suggested-action")
        self.run_button.connect("clicked", self._on_run_clicked)
        header.pack_end(self.run_button)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_margin_start(16)
        content.set_margin_end(16)

        tasks_group = Adw.PreferencesGroup(title="Bakım Görevleri")
        for task in TASKS:
            row = Adw.ActionRow(title=task.label)
            subtitle_bits = []
            if task.needs_root:
                subtitle_bits.append("root yetkisi gerekir")
            if task.requires_binary:
                subtitle_bits.append(f"'{task.requires_binary}' kurulu olmalı")
            if subtitle_bits:
                row.set_subtitle(" · ".join(subtitle_bits))

            check = Gtk.CheckButton()
            check.set_active(True)
            row.add_prefix(check)
            row.set_activatable_widget(check)

            tasks_group.add(row)
            self._checkbuttons[task.id] = check

        content.append(tasks_group)

        self.status_label = Gtk.Label(label="Hazır", xalign=0)
        content.append(self.status_label)

        self.progress_bar = Gtk.ProgressBar()
        content.append(self.progress_bar)

        self.log_buffer = Gtk.TextBuffer()
        log_view = Gtk.TextView(buffer=self.log_buffer)
        log_view.set_editable(False)
        log_view.set_monospace(True)
        log_view.set_cursor_visible(False)
        log_view.set_left_margin(6)
        log_view.set_top_margin(6)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_child(log_view)
        scrolled.set_vexpand(True)
        scrolled.set_min_content_height(220)
        scrolled.add_css_class("card")
        self._log_view = log_view
        content.append(scrolled)

        toolbar_view.set_content(content)
        self.set_content(toolbar_view)

    # ------------------------------------------------------------------
    # Görev seçimi
    # ------------------------------------------------------------------
    def _on_select_all_clicked(self, _button):
        make_active = not all(cb.get_active() for cb in self._checkbuttons.values())
        for cb in self._checkbuttons.values():
            cb.set_active(make_active)

    # ------------------------------------------------------------------
    # Bakımı başlat / durdur
    # ------------------------------------------------------------------
    def _on_run_clicked(self, _button):
        if self.runner.is_running():
            return

        selected = [t for t in TASKS if self._checkbuttons[t.id].get_active()]
        if not selected:
            self._on_output("Hiçbir görev seçilmedi.\n")
            return

        self.log_buffer.set_text("")

        runnable = []
        for task in selected:
            if task.requires_binary and shutil.which(task.requires_binary) is None:
                self._on_output(
                    f"[Atlandı] {task.label}: '{task.requires_binary}' sistemde bulunamadı.\n"
                )
                continue
            runnable.append(task)

        if not runnable:
            self._on_output("Çalıştırılacak görev kalmadı.\n")
            return

        root_tasks = [t for t in runnable if t.needs_root]
        user_tasks = [t for t in runnable if not t.needs_root]

        queue = []
        if root_tasks:
            queue.append(self._build_root_batch_task(root_tasks))
        queue.extend(user_tasks)

        self._queue_total = len(queue)
        self._queue_done = 0
        self.progress_bar.set_fraction(0.0)
        self.run_button.set_sensitive(False)
        self.stop_button.set_sensitive(True)
        self.status_label.set_label("Bakım başlatılıyor…")

        self.runner.run(queue)

    def _build_root_batch_task(self, root_tasks):
        """Root gerektiren tüm görevleri tek bir betikte birleştirip
        tek bir pkexec çağrısı haline getirir (tek parola istemi)."""
        lines = [
            "#!/bin/bash",
            "set -o pipefail",
            # needrestart / apt gibi araçların interaktif (TTY bekleyen)
            # diyalog açıp betiği kilitlemesini engeller.
            "export DEBIAN_FRONTEND=noninteractive",
            "export NEEDRESTART_MODE=a",
            "",
        ]
        for task in root_tasks:
            lines.append(f'echo "{STEP_MARKER}{task.label}"')
            lines.append(
                f"{task.command} || echo '[HATA] {task.label} basarisiz oldu, devam ediliyor'"
            )
            lines.append("")
        script = "\n".join(lines)

        fd, path = tempfile.mkstemp(prefix="ubuntu-bakim-", suffix=".sh")
        with os.fdopen(fd, "w") as f:
            f.write(script)
        os.chmod(path, 0o700)
        self._temp_script_path = path

        return Task(
            id="root_batch",
            label=f"Root gerektiren işlemler ({len(root_tasks)} görev)",
            command=f"pkexec bash {shlex.quote(path)}",
            needs_root=True,
        )

    def _on_stop_clicked(self, _button):
        self.runner.stop()
        self.status_label.set_label("Durduruluyor…")
        self.stop_button.set_sensitive(False)

    # ------------------------------------------------------------------
    # TaskRunner geri çağrıları (ana thread'de, GLib.idle_add üzerinden çalışır)
    # ------------------------------------------------------------------
    def _on_output(self, text):
        if text.startswith(STEP_MARKER):
            substep = text[len(STEP_MARKER):].strip()
            self.status_label.set_label(f"Çalışıyor: {substep}")
            self._append_log(f"\n>> {substep}\n")
        else:
            self._append_log(text)
        return False

    def _append_log(self, text):
        end_iter = self.log_buffer.get_end_iter()
        self.log_buffer.insert(end_iter, text)
        mark = self.log_buffer.create_mark(None, self.log_buffer.get_end_iter(), False)
        self._log_view.scroll_to_mark(mark, 0.0, False, 0.0, 1.0)

    def _on_task_start(self, task):
        self.status_label.set_label(f"Çalışıyor: {task.label}")
        self._append_log(f"\n=== {task.label} ===\n")
        return False

    def _on_task_done(self, task, returncode):
        self._queue_done += 1
        if self._queue_total:
            self.progress_bar.set_fraction(min(1.0, self._queue_done / self._queue_total))
        status = "tamamlandı" if returncode == 0 else f"hata (kod {returncode})"
        self._append_log(f"--- {task.label}: {status} ---\n")
        return False

    def _on_all_done(self):
        self.progress_bar.set_fraction(1.0)
        self.status_label.set_label("Bakım tamamlandı")
        self.run_button.set_sensitive(True)
        self.stop_button.set_sensitive(False)
        self._cleanup_temp_script()
        return False

    def _cleanup_temp_script(self):
        if self._temp_script_path and os.path.exists(self._temp_script_path):
            try:
                os.remove(self._temp_script_path)
            except OSError:
                pass
        self._temp_script_path = None


class MaintenanceApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.devrim.UbuntuBakimAraci")

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = MaintenanceWindow(self)
        win.present()


def main():
    app = MaintenanceApp()
    return app.run(None)


if __name__ == "__main__":
    raise SystemExit(main())
