from __future__ import annotations

from pathlib import Path

from droidtrace.recording import LogRecorder


def test_recorder_writes_utf8_raw_lines_and_closes_on_stop(tmp_path: Path) -> None:
    recorder = LogRecorder(tmp_path, session_id="session-1")
    target = recorder.start(tmp_path / "capture.log")

    recorder.write("linha café")
    recorder.write("second line\n")
    stopped = recorder.stop()

    assert stopped == target
    assert target.read_text(encoding="utf-8") == "linha café\nsecond line\n"
    assert recorder.is_recording is False


def test_stop_is_idempotent(tmp_path: Path) -> None:
    recorder = LogRecorder(tmp_path, session_id="session-1")
    recorder.start(tmp_path / "capture.log")

    first = recorder.stop()
    second = recorder.stop()

    assert first == tmp_path / "capture.log"
    assert second == first


def test_start_uses_log_subdirectory_and_session_id(tmp_path: Path) -> None:
    recorder = LogRecorder(tmp_path, session_id="session-1")

    target = recorder.start()

    assert target.parent == tmp_path / "logs"
    assert target.name.startswith("session-1-")
    assert target.suffix == ".log"
    recorder.stop()


def test_context_manager_stops_active_recording(tmp_path: Path) -> None:
    with LogRecorder(tmp_path, session_id="session-1") as recorder:
        target = recorder.start()
        recorder.write("persist me")

    assert target.read_text(encoding="utf-8") == "persist me\n"
    assert recorder.is_recording is False
