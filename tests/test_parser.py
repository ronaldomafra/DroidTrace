from __future__ import annotations

from droidtrace.parser import parse_log_line, style_for_priority


def test_parser_extracts_threadtime_fields():
    entry = parse_log_line("08-21 10:12:13.123  1234  5678 E MyTag: boom")

    assert entry.timestamp == "08-21 10:12:13.123"
    assert entry.pid == 1234
    assert entry.tid == 5678
    assert entry.priority == "E"
    assert entry.tag == "MyTag"
    assert entry.message == "boom"
    assert entry.raw == "08-21 10:12:13.123  1234  5678 E MyTag: boom"


def test_parser_preserves_unparseable_line():
    entry = parse_log_line("java.lang.IllegalStateException: boom")

    assert entry.timestamp is None
    assert entry.pid is None
    assert entry.priority is None
    assert entry.tag is None
    assert entry.message == "java.lang.IllegalStateException: boom"


def test_style_for_priority_uses_documented_colors():
    assert style_for_priority("V") == "dim white"
    assert style_for_priority("D") == "blue"
    assert style_for_priority("I") == "green"
    assert style_for_priority("W") == "yellow"
    assert style_for_priority("E") == "bold red"
    assert style_for_priority("F") == "bold bright_red"
    assert style_for_priority(None) == "white"
