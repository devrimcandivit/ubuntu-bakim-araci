"""Görevleri arayüzü kilitlemeden, arka planda bir thread üzerinde çalıştırır.

GTK arayüzüne yalnızca ana thread'den dokunulabildiği için, bu thread
içindeki her geri çağrı GLib.idle_add ile ana thread'in olay döngüsüne
aktarılır.
"""

import subprocess
import threading

from gi.repository import GLib


class TaskRunner:
    def __init__(self, on_output, on_task_start, on_task_done, on_all_done):
        self.on_output = on_output          # (str) -> None
        self.on_task_start = on_task_start  # (Task) -> None
        self.on_task_done = on_task_done    # (Task, int) -> None
        self.on_all_done = on_all_done      # () -> None

        self._process = None
        self._stop_requested = threading.Event()
        self._thread = None

    def is_running(self):
        return self._thread is not None and self._thread.is_alive()

    def run(self, tasks):
        if self.is_running():
            return
        self._stop_requested.clear()
        self._thread = threading.Thread(target=self._run_all, args=(list(tasks),), daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_requested.set()
        if self._process is not None:
            try:
                self._process.terminate()
            except ProcessLookupError:
                pass

    def _run_all(self, tasks):
        for task in tasks:
            if self._stop_requested.is_set():
                break
            GLib.idle_add(self.on_task_start, task)
            returncode = self._run_command(task.command)
            GLib.idle_add(self.on_task_done, task, returncode)
        GLib.idle_add(self.on_all_done)

    def _run_command(self, command):
        try:
            self._process = subprocess.Popen(
                command,
                shell=True,
                executable="/bin/bash",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except OSError as exc:
            GLib.idle_add(self.on_output, f"[HATA] Komut başlatılamadı: {exc}\n")
            return -1

        for line in self._process.stdout:
            GLib.idle_add(self.on_output, line)

        self._process.wait()
        returncode = self._process.returncode
        self._process = None
        return returncode
