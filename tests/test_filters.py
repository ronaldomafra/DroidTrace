from __future__ import annotations

from droidtrace.filters import LogBuffer, LogFilters
from droidtrace.models import LogEntry


def entry(*, priority="I", tag="App", pid=10, message="message"):
    return LogEntry(raw=message, priority=priority, tag=tag, pid=pid, message=message)


def test_buffer_discards_oldest_entry_at_capacity():
    buffer = LogBuffer(max_lines=2)
    buffer.extend([entry(message="one"), entry(message="two"), entry(message="three")])

    assert [item.message for item in buffer] == ["two", "three"]


def test_filters_combine_level_tag_pid_and_text_with_and():
    entries = [
        entry(priority="W", tag="Network", pid=42, message="request timeout"),
        entry(priority="W", tag="Network", pid=42, message="connected"),
        entry(priority="E", tag="Network", pid=99, message="request timeout"),
        entry(priority="I", tag="Network", pid=42, message="request timeout"),
    ]
    filters = LogFilters(min_level="W", tag_query="network", pid=42, search_query="TIMEOUT")

    assert [item.message for item in filters.apply(entries)] == ["request timeout"]


def test_invalid_regex_returns_error_without_replacing_previous_regex():
    filters = LogFilters(regex_pattern="timeout")

    error = filters.set_regex("[")

    assert error is not None
    assert [item.message for item in filters.apply([entry(message="timeout")])] == ["timeout"]




def test_package_pid_set_matches_every_process_of_the_package():
    from droidtrace.filters import LogFilters
    from droidtrace.models import LogEntry

    filters = LogFilters(pids=frozenset({101, 202}))
    entries = [
        LogEntry(raw="one", pid=101, message="main"),
        LogEntry(raw="two", pid=202, message="worker"),
        LogEntry(raw="three", pid=303, message="other"),
    ]

    assert [entry.message for entry in filters.apply(entries)] == ["main", "worker"]


def test_regex_filter_limits_entries():
    filters = LogFilters(regex_pattern=r"error \d+")

    assert [item.message for item in filters.apply([entry(message="error 42"), entry(message="error")])] == ["error 42"]
