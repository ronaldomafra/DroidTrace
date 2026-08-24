from __future__ import annotations

from queue import Queue
from time import monotonic
from unittest.mock import patch

import pytest


class FakeStream:
    def __init__(self) -> None:
        self.events: Queue[str] = Queue()
        self.started = False
        self.stopped = False
        self.client = type("FakeClient", (), {"package_pids": lambda _self, _package: [1234, 5678]})()

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def restart(self, serial=None) -> None:
        self.stop()
        self.start()

    def clear_device_logs(self) -> None:
        return None


class FakeAnalyzer:
    def __init__(self) -> None:
        self.calls = []

    def analyze(self, entries, user_prompt: str) -> str:
        self.calls.append((list(entries), user_prompt))
        return "Análise: timeout de rede detectado."


class FailingAnalyzer:
    def analyze(self, entries, user_prompt: str) -> str:
        raise RuntimeError("Codex indisponível")


@pytest.mark.asyncio
async def test_prompt_remains_focused_after_filter_command():
    from logcat_manager.app import LogcatApp

    app = LogcatApp(stream=FakeStream(), auto_start=False)
    async with app.run_test() as pilot:
        await pilot.click("#command-input")
        await pilot.press(":", "l", "e", "v", "e", "l", " ", "E", "enter")
        assert app.filters.min_level == "E"
        assert app.query_one("#command-input").has_focus


@pytest.mark.asyncio
async def test_slash_command_menu_is_visible_and_clickable():
    from textual.widgets import Input, OptionList

    from logcat_manager.app import LogcatApp

    app = LogcatApp(stream=FakeStream(), auto_start=False)
    async with app.run_test() as pilot:
        menu = app.query_one("#command-menu", OptionList)
        command_input = app.query_one("#command-input", Input)
        assert menu.display is False
        command_input.value = "/"
        await pilot.pause()
        assert menu.display is True
        assert menu.option_count >= 5
        assert str(menu.get_option_at_index(0).prompt) == "/help"

        command_input.value = "/level E"
        await pilot.pause()
        await pilot.press("enter")

        assert app.filters.min_level == "E"
        assert command_input.has_focus


@pytest.mark.asyncio
async def test_package_command_resolves_all_package_processes():
    from textual.widgets import Input

    from logcat_manager.app import LogcatApp

    app = LogcatApp(stream=FakeStream(), auto_start=False)
    async with app.run_test() as pilot:
        command_input = app.query_one("#command-input", Input)
        command_input.value = "/package br.com.tbs.afv.multiplatform"
        await pilot.pause()
        await pilot.press("enter")

        assert app.filters.pids == frozenset({1234, 5678})
        assert app.package_name == "br.com.tbs.afv.multiplatform"


@pytest.mark.asyncio
async def test_model_command_persists_and_updates_codex_analyzer(tmp_path):
    from logcat_manager.app import LogcatApp

    analyzer = FakeAnalyzer()
    app = LogcatApp(stream=FakeStream(), analyzer=analyzer, config_path=tmp_path / "config.json", auto_start=False)
    async with app.run_test():
        app._execute("/model gpt-5.4")

        assert app.config.codex_model == "gpt-5.4"
        assert analyzer.model == "gpt-5.4"


@pytest.mark.asyncio
async def test_help_replaces_log_view_with_usage_reference():
    from textual.widgets import Input

    from logcat_manager.app import LogcatApp

    app = LogcatApp(stream=FakeStream(), auto_start=False)
    async with app.run_test() as pilot:
        command_input = app.query_one("#command-input", Input)
        command_input.value = "/help"
        await pilot.pause()
        await pilot.press("enter")

        assert app.showing_help is True
        assert any("/package" in line for line in app.help_lines())


@pytest.mark.asyncio
async def test_analise_sends_visible_logs_and_displays_codex_result():
    from textual.widgets import Input

    from logcat_manager.app import LogcatApp

    analyzer = FakeAnalyzer()
    app = LogcatApp(stream=FakeStream(), analyzer=analyzer, auto_start=False)
    app.add_log_line("08-21 10:00:00.000  123  123 E Network: timeout")
    async with app.run_test() as pilot:
        command_input = app.query_one("#command-input", Input)
        command_input.value = "/analise priorize rede"
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause(0.1)

        assert app.analysis_text == "Análise: timeout de rede detectado."
        assert len(app.analysis_history) == 1
        assert app.analysis_history[0].prompt == "priorize rede"
        assert analyzer.calls[0][1] == "priorize rede"
        assert "Network: timeout" in analyzer.calls[0][0][0].raw

        app._execute("/logs")
        assert app.analysis_text is None

        app._execute("/analises")
        assert app.showing_analysis_history is True

        app._execute("/ver 1")
        assert app.current_analysis_number == 1
        assert app.analysis_text == "Análise: timeout de rede detectado."


@pytest.mark.asyncio
async def test_analise_error_is_shown_in_log_view_without_error_toast():
    from textual.widgets import Input

    from logcat_manager.app import LogcatApp

    app = LogcatApp(stream=FakeStream(), analyzer=FailingAnalyzer(), auto_start=False)
    app.add_log_line("08-21 10:00:00.000  123  123 E Network: timeout")
    async with app.run_test() as pilot:
        command_input = app.query_one("#command-input", Input)
        command_input.value = "/analise"
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause(0.1)

        assert app.analysis_text == "ANÁLISE CODEX FALHOU\nCodex indisponível"


@pytest.mark.asyncio
async def test_local_clear_requires_confirm():
    from logcat_manager.app import LogcatApp

    app = LogcatApp(stream=FakeStream(), auto_start=False)
    app.add_log_line("08-21 10:12:13.123  1234  5678 E MyTag: boom")
    async with app.run_test() as pilot:
        await pilot.click("#command-input")
        await pilot.press(":", "c", "l", "e", "a", "r", "enter")
        assert len(app.buffer) == 1
        await pilot.press(":", "c", "l", "e", "a", "r", " ", "c", "o", "n", "f", "i", "r", "m", "enter")
        assert len(app.buffer) == 0


@pytest.mark.asyncio
async def test_rendering_a_log_line_does_not_raise():
    from logcat_manager.app import LogcatApp

    app = LogcatApp(stream=FakeStream(), auto_start=False)
    async with app.run_test():
        app.add_log_line("08-21 10:12:13.123  1234  5678 E MyTag: boom")
        assert len(app.buffer) == 1


@pytest.mark.asyncio
async def test_live_logs_append_without_repainting_the_entire_view():
    from textual.widgets import RichLog

    from logcat_manager.app import LogcatApp

    app = LogcatApp(stream=FakeStream(), auto_start=False)
    async with app.run_test():
        log = app.query_one("#log-view", RichLog)
        with patch.object(log, "clear") as clear:
            app.add_log_line("08-21 10:12:13.123  1234  5678 I MyTag: incremental")
            clear.assert_not_called()


@pytest.mark.asyncio
async def test_manual_scroll_pauses_follow_then_resumes_after_idle():
    from textual import events
    from textual.widgets import RichLog

    from logcat_manager.app import LogcatApp

    app = LogcatApp(stream=FakeStream(), auto_start=False)
    async with app.run_test():
        log = app.query_one("#log-view", RichLog)
        event = events.MouseScrollUp(log, 0, 0, 0, 1, 0, False, False, False)
        app.on_mouse_scroll_up(event)
        assert app.following is False

        app.last_manual_scroll_at = monotonic() - app.AUTO_FOLLOW_IDLE_SECONDS
        app._resume_follow_after_idle()
        assert app.following is True


def test_drain_processes_only_one_bounded_batch_per_tick():
    from logcat_manager.app import LogcatApp

    stream = FakeStream()
    for number in range(500):
        stream.events.put(f"08-21 10:12:13.123  1234  5678 I Test: log {number}")
    app = LogcatApp(stream=stream, auto_start=False)

    app._drain_stream()

    assert len(app.buffer) == app.MAX_LINES_PER_TICK
    assert stream.events.qsize() == 500 - app.MAX_LINES_PER_TICK


def test_render_window_is_bounded_to_keep_large_buffers_responsive():
    from logcat_manager.app import LogcatApp

    app = LogcatApp(stream=FakeStream(), auto_start=False)
    for number in range(10_000):
        app.add_log_line(f"08-21 10:12:13.123  1234  5678 I Test: log {number}")

    entries = app.entries_for_render()

    assert len(entries) == app.MAX_RENDERED_LINES
    assert entries[0].message == f"log {10_000 - app.MAX_RENDERED_LINES}"
    assert entries[-1].message == "log 9999"
