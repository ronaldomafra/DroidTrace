from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LogEntry:
    raw: str
    timestamp: str | None = None
    pid: int | None = None
    tid: int | None = None
    priority: str | None = None
    tag: str | None = None
    message: str = ""
