from __future__ import annotations

import re

from .models import LogEntry

_THREADTIME_RE = re.compile(
    r"^(?P<timestamp>\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d{3})\s+"
    r"(?P<pid>\d+)\s+(?P<tid>\d+)\s+(?P<priority>[VDIWEF])\s+"
    r"(?P<tag>[^:]+):\s?(?P<message>.*)$"
)

_PRIORITY_STYLES = {
    "V": "dim white",
    "D": "blue",
    "I": "green",
    "W": "yellow",
    "E": "bold red",
    "F": "bold bright_red",
}


def parse_log_line(line: str) -> LogEntry:
    raw = line.rstrip("\r\n")
    match = _THREADTIME_RE.match(raw)
    if not match:
        return LogEntry(raw=raw, message=raw)
    fields = match.groupdict()
    return LogEntry(
        raw=raw,
        timestamp=fields["timestamp"],
        pid=int(fields["pid"]),
        tid=int(fields["tid"]),
        priority=fields["priority"],
        tag=fields["tag"].strip(),
        message=fields["message"],
    )


def style_for_priority(priority: str | None) -> str:
    return _PRIORITY_STYLES.get(priority or "", "white")
