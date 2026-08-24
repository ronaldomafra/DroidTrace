from __future__ import annotations

from types import SimpleNamespace

import pytest

from droidtrace.adb import AdbClient, AdbDevice, AdbLogcatStream


class FakeProcess:
    def __init__(self, stdout=("line one\n", "line two\n")):
        self.stdout = iter(stdout)
        self.stderr = iter(())
        self.returncode = None
        self.terminated = False
        self.waited = False
        self.killed = False

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = 0

    def wait(self, timeout=None):
        self.waited = True
        return self.returncode

    def kill(self):
        self.killed = True
        self.returncode = -9


def test_list_devices_parses_only_device_rows(monkeypatch):
    def fake_run(args, **kwargs):
        assert args == ["adb", "devices"]
        assert kwargs["shell"] is False
        return SimpleNamespace(stdout="List of devices attached\nemulator-5554\tdevice\nABC\toffline\n\n")

    monkeypatch.setattr("droidtrace.adb.subprocess.run", fake_run)

    assert AdbClient("adb").list_devices() == [AdbDevice("emulator-5554", "device"), AdbDevice("ABC", "offline")]


def test_start_stream_uses_threadtime_and_serial_without_shell(monkeypatch):
    process = FakeProcess(())
    calls = []

    def fake_popen(args, **kwargs):
        calls.append((args, kwargs))
        return process

    monkeypatch.setattr("droidtrace.adb.subprocess.Popen", fake_popen)
    stream = AdbLogcatStream("C:/sdk/adb.exe", serial="emulator-5554")

    stream.start()

    assert calls[0][0] == ["C:/sdk/adb.exe", "-s", "emulator-5554", "logcat", "-v", "threadtime"]
    assert calls[0][1]["shell"] is False
    stream.stop()


def test_stream_reader_enqueues_stdout_lines(monkeypatch):
    monkeypatch.setattr("droidtrace.adb.subprocess.Popen", lambda *args, **kwargs: FakeProcess())
    stream = AdbLogcatStream("adb")

    stream.start()
    assert stream.lines.get(timeout=1) == "line one"
    assert stream.lines.get(timeout=1) == "line two"
    stream.stop()


def test_stop_is_idempotent_and_restart_starts_new_process(monkeypatch):
    processes = [FakeProcess(()), FakeProcess(())]
    monkeypatch.setattr("droidtrace.adb.subprocess.Popen", lambda *args, **kwargs: processes.pop(0))
    stream = AdbLogcatStream("adb")

    stream.start()
    first = stream.process
    stream.stop()
    stream.stop()
    stream.restart()

    assert first.terminated is True
    assert stream.process is not first
    stream.stop()


def test_clear_logs_invokes_adb_logcat_clear_without_shell(monkeypatch):
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("droidtrace.adb.subprocess.run", fake_run)

    AdbClient("adb", serial="ABC").clear_logs()

    assert calls == [(["adb", "-s", "ABC", "logcat", "-c"], {"capture_output": True, "text": True, "shell": False, "check": True})]




def test_validate_executable_reports_missing_command(monkeypatch):
    monkeypatch.setattr("droidtrace.adb.shutil.which", lambda _: None)

    with pytest.raises(FileNotFoundError):
        AdbClient("missing-adb").validate_executable()




def test_stream_drops_oldest_lines_when_queue_is_full():
    stream = AdbLogcatStream("adb", max_queue_lines=2)

    stream._enqueue_line(stream.lines, "first")
    stream._enqueue_line(stream.lines, "second")
    stream._enqueue_line(stream.lines, "third")

    assert stream.lines.get_nowait() == "second"
    assert stream.lines.get_nowait() == "third"


def test_package_pids_uses_adb_pidof_for_selected_device(monkeypatch):
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(stdout="1234 5678\n")

    monkeypatch.setattr("droidtrace.adb.subprocess.run", fake_run)

    assert AdbClient("adb", serial="ABC").package_pids("br.com.tbs.afv.multiplatform") == [1234, 5678]
    assert calls == [
        (["adb", "-s", "ABC", "shell", "pidof", "br.com.tbs.afv.multiplatform"],
         {"capture_output": True, "text": True, "shell": False, "check": True})
    ]
