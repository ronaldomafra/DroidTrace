from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace

from logcat_manager.analysis import CodexAnalyzer
from logcat_manager.models import LogEntry


def test_analyzer_sends_visible_logs_and_optional_prompt_to_codex(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(shutil, "which", lambda _: "C:/npm/codex.CMD")

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        output_path = Path(args[args.index("--output-last-message") + 1])
        output_path.write_text("Resumo: erro de rede.", encoding="utf-8")
        return SimpleNamespace(returncode=0, stderr="")

    analyzer = CodexAnalyzer(runner=fake_run, temp_dir=tmp_path)
    result = analyzer.analyze(
        [
            LogEntry(raw="08-21 10:00:00.000  123  123 E Network: timeout"),
            LogEntry(raw="08-21 10:00:01.000  123  123 W Network: retry"),
        ],
        user_prompt="priorize erros de rede",
    )

    assert result == "Resumo: erro de rede."
    args, kwargs = calls[0]
    assert args[:3] == ["C:/npm/codex.CMD", "exec", "--ephemeral"]
    assert "--skip-git-repo-check" in args
    assert "read-only" in args
    assert args[-1] == "-"
    assert "priorize erros de rede" in kwargs["input"]
    assert "Network: timeout" in kwargs["input"]
    assert kwargs["timeout"] == 120
    assert kwargs["encoding"] == "utf-8"
    assert kwargs["errors"] == "replace"
    assert kwargs["cwd"] == str(tmp_path)
