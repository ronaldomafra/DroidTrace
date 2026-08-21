from __future__ import annotations

from queue import Queue

import pytest


class FakeStream:
    def __init__(self) -> None:
        self.events: Queue[str] = Queue()
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def restart(self, serial=None) -> None:
        self.stop()
        self.start()

    def clear_device_logs(self) -> None:
        return None


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


def test_drain_processes_only_one_bounded_batch_per_tick():
    from logcat_manager.app import LogcatApp

    stream = FakeStream()
    for number in range(500):
        stream.events.put(f"08-21 10:12:13.123  1234  5678 I Test: log {number}")
    app = LogcatApp(stream=stream, auto_start=False)

    app._drain_stream()

    assert len(app.buffer) == app.MAX_LINES_PER_TICK
    assert stream.events.qsize() == 500 - app.MAX_LINES_PER_TICK
