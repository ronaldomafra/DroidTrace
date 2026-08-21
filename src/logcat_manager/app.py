from __future__ import annotations

from pathlib import Path
from queue import Empty
from typing import Any

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import Footer, Header, Input, RichLog, Static

from .config import AppConfig, save_config
from .filters import LogBuffer, LogFilters
from .parser import parse_log_line, style_for_priority


class LogcatApp(App[None]):
    """Interactive terminal interface for a local ADB logcat stream."""

    MAX_LINES_PER_TICK = 200
    MAX_RENDERED_LINES = 2_000

    CSS = """
    #log-view { height: 1fr; border: round $primary; }
    #status { height: 1; background: $panel; color: $text; }
    #command-input { dock: bottom; }
    """
    BINDINGS = [("ctrl+c", "quit", "Quit"), ("q", "quit", "Quit"), ("end", "follow", "Follow")]

    def __init__(
        self,
        stream: Any | None = None,
        *,
        config: AppConfig | None = None,
        config_path: Path | None = None,
        auto_start: bool = True,
    ) -> None:
        super().__init__()
        self.config = config or AppConfig()
        self.config_path = config_path
        self.stream = stream
        self.auto_start = auto_start
        self.buffer = LogBuffer(self.config.max_buffer_lines)
        self.filters = LogFilters()
        self.paused = False
        self.following = True
        self.command_history: list[str] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical():
            yield RichLog(id="log-view", highlight=True, markup=True, wrap=True)
            yield Static(id="status")
            yield Input(placeholder="Digite :help para comandos ou texto para pesquisar", id="command-input")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#command-input", Input).focus()
        if self.stream is None and self.auto_start:
            try:
                from .adb import AdbLogcatStream
                self.stream = AdbLogcatStream(self.config.adb_path or "adb", serial=self.config.serial)
            except Exception as error:
                self.notify(f"ADB indisponível: {error}", severity="error")
        if self.stream is not None and self.auto_start:
            try:
                self.stream.start()
            except Exception as error:
                self.notify(f"Não foi possível iniciar logcat: {error}", severity="error")
        self.set_interval(0.1, self._drain_stream)
        self._update_status()

    def on_unmount(self) -> None:
        if self.stream is not None:
            self.stream.stop()

    def _drain_stream(self) -> None:
        if self.stream is None:
            return
        lines = getattr(self.stream, "lines", getattr(self.stream, "events", None))
        if lines is None:
            return
        processed = 0
        while processed < self.MAX_LINES_PER_TICK:
            try:
                line = lines.get_nowait()
            except Empty:
                break
            self.buffer.append(parse_log_line(line))
            processed += 1
        if processed and not self.paused and self._screen_stack:
            self._render_logs()

    def add_log_line(self, line: str) -> None:
        self.buffer.append(parse_log_line(line))
        if not self.paused and self._screen_stack:
            self._render_logs()

    def entries_for_render(self) -> list[Any]:
        """Return the newest filtered entries that fit the responsive view."""
        return self.filters.apply(self.buffer)[-self.MAX_RENDERED_LINES :]

    def _render_logs(self) -> None:
        log = self.query_one("#log-view", RichLog)
        log.clear()
        visible = self.entries_for_render()
        for entry in visible:
            log.write(Text(entry.raw, style=style_for_priority(entry.priority)))
        if self.following:
            log.scroll_end(animate=False)
        self._update_status(visible_count=len(visible))

    def _update_status(self, visible_count: int | None = None) -> None:
        if not self.is_mounted:
            return
        visible = visible_count if visible_count is not None else len(self.filters.apply(self.buffer))
        active = []
        if self.filters.min_level:
            active.append(f"level≥{self.filters.min_level}")
        if self.filters.tag_query:
            active.append(f"tag={self.filters.tag_query}")
        if self.filters.pid is not None:
            active.append(f"pid={self.filters.pid}")
        if self.filters.search_query:
            active.append(f"find={self.filters.search_query}")
        if self.filters.regex_pattern:
            active.append(f"regex={self.filters.regex_pattern}")
        state = "paused" if self.paused else "live"
        self.query_one("#status", Static).update(
            f"{state} | {visible}/{len(self.buffer)} linhas | {'; '.join(active) or 'sem filtros'}"
        )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        command = event.value.strip()
        event.input.value = ""
        if command:
            self.command_history.append(command)
            self._execute(command)
        event.input.focus()

    def _execute(self, text: str) -> None:
        if not text.startswith(":"):
            self.filters.search_query = text or None
            self._render_logs()
            return
        name, _, argument = text[1:].partition(" ")
        name, argument = name.lower(), argument.strip()
        if name == "level":
            self.filters.min_level = None if argument.lower() == "all" else argument.upper()
        elif name == "tag":
            self.filters.tag_query = None if argument.lower() == "clear" else argument or None
        elif name == "pid":
            try:
                self.filters.pid = None if argument.lower() == "clear" else int(argument)
            except ValueError:
                self.notify("PID deve ser um número ou clear", severity="error")
                return
        elif name == "find":
            self.filters.search_query = None if argument.lower() == "clear" else argument or None
        elif name == "regex":
            error = self.filters.set_regex(None if argument.lower() == "clear" else argument)
            if error:
                self.notify(error, severity="error")
                return
        elif name == "clear":
            if argument != "confirm":
                self.notify("Use :clear confirm para limpar somente o buffer local", severity="warning")
                return
            self.buffer.clear()
        elif name == "pause":
            self.paused = True
        elif name == "resume":
            self.paused = False
        elif name == "follow":
            self.following = True
        elif name == "restart" and self.stream is not None:
            self.stream.restart()
        elif name == "device" and self.stream is not None:
            self.config = AppConfig(self.config.adb_path, argument or None, self.config.max_buffer_lines)
            if hasattr(self.stream, "client"):
                self.stream.client.serial = self.config.serial
                self.stream.restart()
            else:
                self.stream.restart(serial=self.config.serial)
        elif name == "config" and argument.startswith("adb "):
            self.config = AppConfig(argument[4:].strip(), self.config.serial, self.config.max_buffer_lines)
            save_config(self.config, self.config_path)
        elif name == "config" and argument == "show":
            self.notify(f"ADB: {self.config.adb_path or 'adb'} | serial: {self.config.serial or 'auto'}")
        elif name == "save":
            self._save_visible(argument)
        elif name == "adb-clear":
            if argument != "confirm":
                self.notify("Use :adb-clear confirm para limpar logs do dispositivo", severity="warning")
                return
            if self.stream is not None:
                if hasattr(self.stream, "clear_device_logs"):
                    self.stream.clear_device_logs()
                elif hasattr(self.stream, "client"):
                    self.stream.client.clear_logs()
                else:
                    self.notify("Stream não suporta limpeza do dispositivo", severity="error")
                    return
                self.notify("Buffer de logs do dispositivo limpo")
        elif name in {"quit", "exit"}:
            self.exit()
        elif name == "help":
            self.notify("Filtros: :level :tag :pid :find :regex | :pause :resume :follow :save :clear :adb-clear :quit")
        else:
            self.notify(f"Comando desconhecido: {name}. Use :help", severity="error")
            return
        self._render_logs()

    def _save_visible(self, target: str) -> None:
        if not target:
            self.notify("Informe um caminho: :save C:/logs/saida.txt", severity="error")
            return
        path = Path(target.strip('"'))
        if path.exists():
            self.notify("Arquivo já existe; escolha outro caminho", severity="warning")
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(entry.raw for entry in self.filters.apply(self.buffer)) + "\n", encoding="utf-8")
        self.notify(f"Logs exportados para {path}")

    def action_follow(self) -> None:
        self.following = True
        self.query_one("#log-view", RichLog).scroll_end(animate=False)
