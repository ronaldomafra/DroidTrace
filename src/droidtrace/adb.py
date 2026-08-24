from __future__ import annotations

import os
import queue
import shutil
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO


@dataclass(frozen=True)
class AdbDevice:
    serial: str
    state: str


class AdbClient:
    def __init__(self, executable: str = "adb", serial: str | None = None) -> None:
        self.executable = executable
        self.serial = serial

    def validate_executable(self) -> str:
        if os.path.sep in self.executable or (os.path.altsep and os.path.altsep in self.executable):
            if Path(self.executable).is_file():
                return self.executable
        elif shutil.which(self.executable):
            return self.executable
        raise FileNotFoundError(f"ADB executable not found: {self.executable}")

    def command(self, *arguments: str) -> list[str]:
        command = [self.executable]
        if self.serial:
            command.extend(("-s", self.serial))
        command.extend(arguments)
        return command

    def list_devices(self) -> list[AdbDevice]:
        result = subprocess.run(
            [self.executable, "devices"], capture_output=True, text=True, shell=False, check=True
        )
        devices: list[AdbDevice] = []
        for line in result.stdout.splitlines():
            if "\t" not in line:
                continue
            serial, state = line.split("\t", 1)
            if serial:
                devices.append(AdbDevice(serial, state.strip()))
        return devices

    def package_pids(self, package_name: str) -> list[int]:
        result = subprocess.run(
            self.command("shell", "pidof", package_name),
            capture_output=True,
            text=True,
            shell=False,
            check=True,
        )
        return [int(pid) for pid in result.stdout.split()]

    def clear_logs(self) -> None:
        subprocess.run(
            self.command("logcat", "-c"), capture_output=True, text=True, shell=False, check=True
        )


class AdbLogcatStream:
    def __init__(self, executable: str = "adb", serial: str | None = None, *, max_queue_lines: int = 5_000) -> None:
        if max_queue_lines <= 0:
            raise ValueError("max_queue_lines must be positive")
        self.client = AdbClient(executable, serial)
        self.lines: queue.Queue[str] = queue.Queue(maxsize=max_queue_lines)
        self.errors: queue.Queue[str] = queue.Queue(maxsize=max_queue_lines)
        self.process: subprocess.Popen[str] | None = None
        self._stop_event = threading.Event()
        self._threads: list[threading.Thread] = []

    def start(self) -> None:
        if self.process is not None and self.process.poll() is None:
            return
        self._stop_event.clear()
        self.process = subprocess.Popen(
            self.client.command("logcat", "-v", "threadtime"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            shell=False,
        )
        self._threads = [
            self._start_reader(self.process.stdout, self.lines),
            self._start_reader(self.process.stderr, self.errors),
        ]

    def stop(self) -> None:
        self._stop_event.set()
        process = self.process
        if process is None:
            return
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        self.process = None

    def restart(self) -> None:
        self.stop()
        self.start()

    def _start_reader(self, source: TextIO | None, destination: queue.Queue[str]) -> threading.Thread:
        thread = threading.Thread(target=self._read_lines, args=(source, destination), daemon=True)
        thread.start()
        return thread

    @staticmethod
    def _enqueue_line(destination: queue.Queue[str], line: str) -> None:
        try:
            destination.put_nowait(line)
        except queue.Full:
            try:
                destination.get_nowait()
            except queue.Empty:
                pass
            destination.put_nowait(line)

    def _read_lines(self, source: TextIO | None, destination: queue.Queue[str]) -> None:
        if source is None:
            return
        for line in source:
            if self._stop_event.is_set():
                return
            self._enqueue_line(destination, line.rstrip("\r\n"))
