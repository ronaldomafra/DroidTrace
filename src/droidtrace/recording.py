from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO


class LogRecorder:
    """Writes incoming raw log lines to an optional UTF-8 recording file."""

    def __init__(self, directory: Path | str, *, session_id: str) -> None:
        self.directory = Path(directory)
        self.session_id = session_id
        self._file: TextIO | None = None
        self._path: Path | None = None
        self._last_path: Path | None = None

    @property
    def is_recording(self) -> bool:
        return self._file is not None

    @property
    def path(self) -> Path | None:
        return self._path

    def start(self, path: Path | str | None = None) -> Path:
        if self._file is not None:
            raise RuntimeError("A recording is already active.")
        target = Path(path) if path is not None else self._default_path()
        target = target.expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        self._file = target.open("a", encoding="utf-8", newline="\n")
        self._path = target
        self._last_path = target
        return target

    def write(self, raw_line: str) -> None:
        if self._file is None:
            return
        self._file.write(raw_line.rstrip("\r\n") + "\n")

    def stop(self) -> Path | None:
        if self._file is not None:
            self._file.flush()
            self._file.close()
            self._file = None
            self._path = None
        return self._last_path

    def close(self) -> Path | None:
        return self.stop()

    def __enter__(self) -> LogRecorder:
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()

    def _default_path(self) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        return self.directory / "logs" / f"{self.session_id}-{timestamp}.log"
