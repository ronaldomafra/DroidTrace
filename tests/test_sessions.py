from __future__ import annotations

import json
from pathlib import Path

from droidtrace.sessions import AnalysisRecord, SessionRepository


def test_create_session_persists_required_metadata(tmp_path: Path) -> None:
    repository = SessionRepository(tmp_path)

    session = repository.create(
        name="Checkout crash",
        provider="codex",
        model="gpt-5",
        device_serial="emulator-5554",
        filters={"min_level": "E", "pids": [42]},
    )

    stored = json.loads((tmp_path / f"{session.id}.json").read_text(encoding="utf-8"))
    assert stored == {
        "id": session.id,
        "name": "Checkout crash",
        "started_at": session.started_at,
        "ended_at": None,
        "provider": "codex",
        "model": "gpt-5",
        "device_serial": "emulator-5554",
        "filters": {"min_level": "E", "pids": [42]},
        "analyses": [],
        "recording_paths": [],
    }


def test_load_restores_analysis_records_without_raw_logs(tmp_path: Path) -> None:
    repository = SessionRepository(tmp_path)
    session = repository.create(name="Network", provider="codex", model=None)
    record = AnalysisRecord(
        created_at="2026-08-24T16:30:00+00:00",
        prompt="Find the error",
        result="Timeout in checkout.",
        model="gpt-5",
    )
    session.analyses.append(record)
    session.recording_paths.append(tmp_path / "network.log")
    repository.save(session)

    restored = repository.load(session.id)

    assert restored is not None
    assert restored.analyses == [record]
    assert restored.recording_paths == [tmp_path / "network.log"]
    assert "raw" not in (tmp_path / f"{session.id}.json").read_text(encoding="utf-8")


def test_recent_lists_newest_sessions_first(tmp_path: Path) -> None:
    repository = SessionRepository(tmp_path)
    older = repository.create(name="Older", provider="codex", model=None)
    newer = repository.create(name="Newer", provider="claude", model="sonnet")
    older.started_at = "2026-01-01T00:00:00+00:00"
    newer.started_at = "2026-01-02T00:00:00+00:00"
    repository.save(older)
    repository.save(newer)

    assert [session.name for session in repository.recent()] == ["Newer", "Older"]


def test_recent_ignores_malformed_session_json(tmp_path: Path) -> None:
    repository = SessionRepository(tmp_path)
    valid = repository.create(name="Valid", provider="codex", model=None)
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")

    assert [session.id for session in repository.recent()] == [valid.id]
    assert repository.load("broken") is None
