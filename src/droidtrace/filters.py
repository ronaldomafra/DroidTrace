from __future__ import annotations

import re
from collections import deque
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field

from .models import LogEntry

_LEVELS = {level: index for index, level in enumerate(("V", "D", "I", "W", "E", "F"))}


class LogBuffer:
    def __init__(self, max_lines: int = 10_000) -> None:
        if max_lines <= 0:
            raise ValueError("max_lines must be positive")
        self._entries: deque[LogEntry] = deque(maxlen=max_lines)

    def append(self, entry: LogEntry) -> None:
        self._entries.append(entry)

    def extend(self, entries: Iterable[LogEntry]) -> None:
        self._entries.extend(entries)

    def clear(self) -> None:
        self._entries.clear()

    def __iter__(self) -> Iterator[LogEntry]:
        return iter(self._entries)

    def __len__(self) -> int:
        return len(self._entries)


@dataclass
class LogFilters:
    min_level: str | None = None
    tag_query: str | None = None
    pid: int | None = None
    pids: frozenset[int] | None = None
    search_query: str | None = None
    regex_pattern: str | None = None
    _regex: re.Pattern[str] | None = field(init=False, default=None, repr=False)

    def __post_init__(self) -> None:
        if self.min_level is not None:
            self.min_level = self.min_level.upper()
            if self.min_level not in _LEVELS:
                raise ValueError("min_level must be one of V, D, I, W, E, F")
        if self.regex_pattern:
            self._regex = re.compile(self.regex_pattern, re.IGNORECASE)

    def set_regex(self, pattern: str | None) -> str | None:
        if not pattern:
            self.regex_pattern = None
            self._regex = None
            return None
        try:
            compiled = re.compile(pattern, re.IGNORECASE)
        except re.error as error:
            return f"invalid regular expression: {error}"
        self.regex_pattern = pattern
        self._regex = compiled
        return None

    def apply(self, entries: Iterable[LogEntry]) -> list[LogEntry]:
        return [entry for entry in entries if self.matches(entry)]

    def matches(self, entry: LogEntry) -> bool:
        if self.min_level:
            if entry.priority not in _LEVELS or _LEVELS[entry.priority] < _LEVELS[self.min_level]:
                return False
        if self.tag_query and self.tag_query.casefold() not in (entry.tag or "").casefold():
            return False
        if self.pid is not None and entry.pid != self.pid:
            return False
        if self.pids is not None and entry.pid not in self.pids:
            return False
        if self.search_query and self.search_query.casefold() not in entry.message.casefold():
            return False
        return not self._regex or bool(self._regex.search(entry.raw))
