from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from queue import Empty
from threading import Thread
from time import monotonic
from typing import Any

from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import Footer, Header, Input, OptionList, RichLog, Static
from textual.widgets.option_list import Option

from .recording import LogRecorder
from .sessions import AnalysisRecord as PersistedAnalysisRecord
from .sessions import Session, SessionRepository
from .analysis import CodexAnalyzer, format_analysis
from .config import AppConfig, default_config_path, save_config
from .configurator import ConfigScreen
from .providers import ProviderSettings, create_analyzer
from .filters import LogBuffer, LogFilters
from .parser import parse_log_line, style_for_priority


@dataclass(frozen=True)
class AnalysisRecord:
    number: int
    created_at: str
    prompt: str
    result: str
    model: str | None


class LogcatApp(App[None]):
    """Interactive terminal interface for a local ADB logcat stream."""

    MAX_LINES_PER_TICK = 100
    MAX_RENDERED_LINES = 1_000
    STATUS_REFRESH_SECONDS = 0.5
    AUTO_FOLLOW_IDLE_SECONDS = 3.0
    COMMANDS = (
        ("help", "Ajuda", "Exibe esta referência na área de logs"),
        ("level", "Nível", "Uso: /level E ou /level all"),
        ("tag", "Tag", "Uso: /tag Activity ou /tag clear"),
        ("pid", "PID", "Uso: /pid 1234 ou /pid clear"),
        ("package", "Package", "Uso: /package br.com.exemplo.app"),
        ("analise", "Análise Codex", "Uso: /analise [foco opcional]"),
        ("analises", "Histórico", "Mostra análises desta sessão"),
        ("ver", "Abrir análise", "Uso: /ver número"),
        ("logs", "Voltar aos logs", "Fecha análise ou histórico"),
        ("sessoes", "Sessões", "Lista sessões gravadas"),
        ("sessao", "Sessão", "Uso: /sessao nova nome | /sessao abrir id"),
        ("gravar", "Gravar logs", "Uso: /gravar iniciar [arquivo] | parar"),
        ("configurar", "Configurador", "Seleciona provider e modelo"),
        ("model", "Modelo", "Uso: /model nome-do-modelo"),
        ("find", "Buscar", "Uso: /find timeout ou /find clear"),
        ("regex", "Regex", "Uso: /regex FATAL.*Exception"),
        ("pause", "Pausar", "Pausa a atualização visual"),
        ("resume", "Continuar", "Retoma a atualização visual"),
        ("follow", "Ir ao fim", "Segue as linhas recentes"),
        ("save", "Exportar", "Uso: /save C:/logs/logcat.txt"),
        ("clear", "Limpar tela", "Limpa somente o buffer local"),
        ("restart", "Reiniciar", "Reinicia a captura ADB"),
        ("quit", "Sair", "Fecha o aplicativo"),
    )

    CSS = """
    #log-view { height: 1fr; border: round $primary; }
    #status { height: 1; background: $panel; color: $text; }
    #command-menu { height: 8; border: round $accent; }
    #command-input { dock: bottom; }
    """
    BINDINGS = [("ctrl+c", "quit", "Quit"), ("q", "quit", "Quit"), ("end", "follow", "Follow")]

    def __init__(
        self,
        stream: Any | None = None,
        analyzer: Any | None = None,
        *,
        config: AppConfig | None = None,
        config_path: Path | None = None,
        auto_start: bool = True,
    ) -> None:
        super().__init__()
        self.config = config or AppConfig()
        self.config_path = config_path
        self.stream = stream
        self.analyzer = analyzer or create_analyzer(ProviderSettings(self.config.provider, self.config.codex_model))
        self.auto_start = auto_start
        self.buffer = LogBuffer(self.config.max_buffer_lines)
        session_dir = Path(self.config.session_dir) if self.config.session_dir else default_config_path().parent / "sessions"
        self.session_repository = SessionRepository(session_dir)
        self.session: Session = self.session_repository.create(
            name="Sessão atual",
            provider=self.config.provider,
            model=self.config.codex_model,
            device_serial=self.config.serial,
        )
        recording_dir = Path(self.config.recording_dir) if self.config.recording_dir else session_dir
        self.recorder = LogRecorder(recording_dir, session_id=self.session.id)
        self.filters = LogFilters()
        self.package_name: str | None = None
        self.showing_help = False
        self.analysis_text: str | None = None
        self.analysis_history: list[AnalysisRecord] = []
        self.current_analysis_number: int | None = None
        self.showing_analysis_history = False
        self.analysis_running = False
        self.paused = False
        self.following = True
        self.last_manual_scroll_at: float | None = None
        self.command_history: list[str] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical():
            yield RichLog(
                id="log-view",
                max_lines=self.MAX_RENDERED_LINES,
                highlight=True,
                markup=True,
                wrap=False,
                auto_scroll=False,
            )
            yield Static(id="status")
            yield OptionList(*self._command_options(), id="command-menu", compact=True)
            yield Input(placeholder="Digite / para comandos ou texto para pesquisar", id="command-input")
        yield Footer()

    def _command_options(self, query: str = "") -> list[Option]:
        normalized = query.removeprefix("/").removeprefix(":").casefold().strip()
        command_prefix = normalized.split(maxsplit=1)[0] if normalized else ""
        matches = [
            (command, label, description)
            for command, label, description in self.COMMANDS
            if not normalized
            or command_prefix in command.casefold()
            or normalized in label.casefold()
            or normalized in description.casefold()
        ]
        return [Option(f"/{command}", id=command) for command, _, _ in matches]

    def help_lines(self) -> list[str]:
        return [
            "DROIDTRACE — comandos",
            "Digite / seguido do comando. Qualquer outro comando volta aos logs.",
            "",
            *[f"/{command:<10} {description}" for command, _, description in self.COMMANDS],
        ]

    def on_input_changed(self, event: Input.Changed) -> None:
        menu = self.query_one("#command-menu", OptionList)
        if event.value.startswith(("/", ":")):
            menu.display = True
            menu.set_options(self._command_options(event.value))
        else:
            menu.display = False

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_id is None:
            return
        command_input = self.query_one("#command-input", Input)
        command_input.value = f"/{event.option_id}"
        command_input.focus()

    def on_mouse_scroll_up(self, event: events.MouseScrollUp) -> None:
        self._pause_follow_for_manual_scroll(event)

    def on_mouse_scroll_down(self, event: events.MouseScrollDown) -> None:
        self._pause_follow_for_manual_scroll(event)

    def _pause_follow_for_manual_scroll(self, event: events.MouseEvent) -> None:
        if not self.is_mounted or event.widget is not self.query_one("#log-view", RichLog):
            return
        self.following = False
        self.last_manual_scroll_at = monotonic()
        self._update_status()

    def _resume_follow_after_idle(self) -> None:
        if self.following or self.last_manual_scroll_at is None:
            return
        if monotonic() - self.last_manual_scroll_at < self.AUTO_FOLLOW_IDLE_SECONDS:
            return
        self.following = True
        self.last_manual_scroll_at = None
        if self.is_mounted:
            self.query_one("#log-view", RichLog).scroll_end(animate=False)
            self._update_status()

    def _open_configurator(self) -> None:
        self.push_screen(
            ConfigScreen(
                ProviderSettings(self.config.provider, self.config.codex_model),
                self.session_repository.directory,
            ),
            self._apply_provider_settings,
        )

    def _apply_provider_settings(self, settings: ProviderSettings | None) -> None:
        if settings is None:
            return
        self.config = AppConfig(
            adb_path=self.config.adb_path,
            serial=self.config.serial,
            max_buffer_lines=self.config.max_buffer_lines,
            codex_model=settings.model,
            provider=settings.provider,
            session_dir=self.config.session_dir,
            recording_dir=self.config.recording_dir,
        )
        self.analyzer = create_analyzer(settings)
        save_config(self.config, self.config_path)
        self.notify(f"Provider: {settings.provider} | modelo: {settings.model}")

    def on_mount(self) -> None:
        self.query_one("#command-input", Input).focus()
        self.query_one("#command-menu", OptionList).display = False
        if self.auto_start and not (self.config_path or default_config_path()).exists():
            self._open_configurator()
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
        path = self.recorder.close()
        if path and path not in self.session.recording_paths:
            self.session.recording_paths.append(path)
        self.session.ended_at = datetime.now().isoformat()
        self.session_repository.save(self.session)
        if self.stream is not None:
            self.stream.stop()

    def _drain_stream(self) -> None:
        if self.stream is None:
            return
        lines = getattr(self.stream, "lines", getattr(self.stream, "events", None))
        if lines is None:
            return
        entries = []
        processed = 0
        while processed < self.MAX_LINES_PER_TICK:
            try:
                line = lines.get_nowait()
            except Empty:
                break
            self.recorder.write(line)
            entries.append(parse_log_line(line))
            processed += 1
        self.buffer.extend(entries)
        if entries and not self.paused and not self.showing_help and not self.analysis_text and self._screen_stack:
            self._append_entries(entries)
        self._resume_follow_after_idle()

    def add_log_line(self, line: str) -> None:
        self.recorder.write(line)
        entry = parse_log_line(line)
        self.buffer.append(entry)
        if not self.paused and not self.showing_help and not self.analysis_text and self._screen_stack:
            self._append_entries([entry])

    def entries_for_render(self) -> list[Any]:
        """Return the newest filtered entries that fit the responsive view."""
        return self.filters.apply(self.buffer)[-self.MAX_RENDERED_LINES :]

    def _append_entries(self, entries: list[Any]) -> None:
        """Append fresh matching entries without rebuilding the RichLog widget."""
        log = self.query_one("#log-view", RichLog)
        for entry in entries:
            if self.filters.matches(entry):
                log.write(
                    Text(entry.raw, style=style_for_priority(entry.priority)),
                    scroll_end=self.following,
                    animate=False,
                )
        self._update_status()

    def _render_logs(self) -> None:
        log = self.query_one("#log-view", RichLog)
        log.clear()
        if self.showing_help:
            for line in self.help_lines():
                log.write(Text(line, style="bold cyan" if line.startswith("LOGCAT") else "white"))
            return
        if self.showing_analysis_history:
            log.write(Text("HISTÓRICO DE ANÁLISES", style="bold magenta"))
            if not self.analysis_history:
                log.write("Nenhuma análise nesta sessão.")
            for record in self.analysis_history:
                focus = record.prompt or "análise padrão"
                model = record.model or "padrão"
                log.write(f"#{record.number}  {record.created_at}  [{model}]  {focus}")
            log.write("")
            log.write("Use /ver N para abrir uma análise ou /logs para voltar.")
            return
        if self.analysis_text:
            record = next((item for item in self.analysis_history if item.number == self.current_analysis_number), None)
            heading = f"ANÁLISE CODEX #{record.number}" if record else "ANÁLISE CODEX"
            log.write(Text(heading, style="bold magenta"))
            if record:
                log.write(f"{record.created_at}  |  modelo: {record.model or 'padrão'}")
            log.write("")
            for title, lines in format_analysis(self.analysis_text):
                log.write(Text(title, style="bold cyan"))
                for line in lines:
                    log.write(Text(line, style="white"))
                log.write("")
            log.write("Use /logs para voltar ou /analises para o histórico.")
            return
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
        if self.package_name:
            active.append(f"package={self.package_name}")
        if self.filters.search_query:
            active.append(f"find={self.filters.search_query}")
        if self.filters.regex_pattern:
            active.append(f"regex={self.filters.regex_pattern}")
        state = "paused" if self.paused else "live"
        self.query_one("#status", Static).update(
            f"{state} | {visible}/{len(self.buffer)} linhas | {'; '.join(active) or 'sem filtros'}"
        )

    def _start_analysis(self, user_prompt: str) -> None:
        entries = self.entries_for_render()
        if not entries:
            self.notify("Não há logs visíveis para analisar.", severity="warning")
            return
        if self.analysis_running:
            self.notify("Uma análise já está em andamento.", severity="warning")
            return
        self.analysis_running = True
        self.analysis_text = None
        self.notify("Enviando logs filtrados para o Codex…")
        Thread(target=self._run_analysis, args=(entries, user_prompt), daemon=True).start()

    def _run_analysis(self, entries: list[Any], user_prompt: str) -> None:
        try:
            result = self.analyzer.analyze(entries, user_prompt)
        except Exception as error:
            self.call_from_thread(self._finish_analysis, None, str(error), user_prompt)
        else:
            self.call_from_thread(self._finish_analysis, result, None, user_prompt)

    def _finish_analysis(self, result: str | None, error: str | None, user_prompt: str) -> None:
        self.analysis_running = False
        if error:
            self.showing_help = False
            self.analysis_text = f"ANÁLISE CODEX FALHOU\n{error}"
            self._render_logs()
            return
        self.showing_help = False
        self.showing_analysis_history = False
        self.analysis_text = result
        record = AnalysisRecord(
            number=len(self.analysis_history) + 1,
            created_at=datetime.now().strftime("%H:%M:%S"),
            prompt=user_prompt,
            result=result or "",
            model=getattr(self.analyzer, "model", self.config.codex_model),
        )
        self.analysis_history.append(record)
        self.session.analyses.append(
            PersistedAnalysisRecord(record.created_at, record.prompt, record.result, record.model, record.number)
        )
        self.session_repository.save(self.session)
        self.current_analysis_number = record.number
        self._render_logs()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        command = event.value.strip()
        event.input.value = ""
        if command:
            self.command_history.append(command)
            self._execute(command)
        event.input.focus()

    def _execute(self, text: str) -> None:
        if text.startswith("/"):
            text = ":" + text[1:]
        if not text.startswith(":"):
            self.showing_help = False
            self.analysis_text = None
            self.filters.search_query = text or None
            self._render_logs()
            return
        name, _, argument = text[1:].partition(" ")
        name, argument = name.lower(), argument.strip()
        if name != "help":
            self.showing_help = False
        if name not in {"analises"}:
            self.showing_analysis_history = False
        if name not in {"analise", "ver"}:
            self.analysis_text = None
        if name == "level":
            self.filters.min_level = None if argument.lower() == "all" else argument.upper()
        elif name == "tag":
            self.filters.tag_query = None if argument.lower() == "clear" else argument or None
        elif name == "pid":
            try:
                self.filters.pid = None if argument.lower() == "clear" else int(argument)
                self.filters.pids = None
                self.package_name = None
            except ValueError:
                self.notify("PID deve ser um número ou clear", severity="error")
                return
        elif name == "package":
            if argument.lower() == "clear":
                self.filters.pids = None
                self.package_name = None
            elif not argument:
                self.notify("Use /package br.com.exemplo.app", severity="error")
                return
            elif self.stream is None or not hasattr(self.stream, "client"):
                self.notify("ADB não está disponível para localizar o package", severity="error")
                return
            else:
                try:
                    pids = self.stream.client.package_pids(argument)
                except Exception as error:
                    self.notify(f"Falha ao localizar package: {error}", severity="error")
                    return
                if not pids:
                    self.notify(f"Package não está em execução: {argument}", severity="warning")
                    return
                self.filters.pid = None
                self.filters.pids = frozenset(pids)
                self.package_name = argument
                self.notify(f"Package {argument}: PID(s) {', '.join(map(str, pids))}")
        elif name == "analise":
            self._start_analysis(argument)
            return
        elif name == "analises":
            self.analysis_text = None
            self.showing_analysis_history = True
        elif name == "ver":
            try:
                number = int(argument)
            except ValueError:
                self.notify("Use /ver número, por exemplo /ver 1", severity="warning")
                return
            record = next((item for item in self.analysis_history if item.number == number), None)
            if record is None:
                self.notify(f"Análise #{number} não existe nesta sessão.", severity="warning")
                return
            self.current_analysis_number = number
            self.analysis_text = record.result
        elif name == "logs":
            self.analysis_text = None
            self.current_analysis_number = None
            self.showing_analysis_history = False
        elif name == "gravar":
            action, _, target = argument.partition(" ")
            if action == "iniciar":
                try:
                    path = self.recorder.start(target or None)
                except RuntimeError as error:
                    self.notify(str(error), severity="warning")
                    return
                self.notify(f"Gravando logs em {path}")
            elif action == "parar":
                path = self.recorder.stop()
                if path:
                    if path not in self.session.recording_paths:
                        self.session.recording_paths.append(path)
                    self.session_repository.save(self.session)
                    self.notify(f"Gravação salva em {path}")
                else:
                    self.notify("Nenhuma gravação ativa.", severity="warning")
            else:
                self.notify("Use /gravar iniciar [arquivo] ou /gravar parar", severity="warning")
                return
        elif name == "sessoes":
            self.analysis_text = "\n".join(
                f"{session.id}  {session.started_at}  {session.name}" for session in self.session_repository.recent(10)
            ) or "Nenhuma sessão gravada."
        elif name == "sessao":
            action, _, value = argument.partition(" ")
            if action == "nova":
                self.session = self.session_repository.create(
                    name=value or "Nova sessão",
                    provider=self.config.provider,
                    model=self.config.codex_model,
                    device_serial=self.config.serial,
                )
                self.recorder = LogRecorder(self.recorder.directory, session_id=self.session.id)
                self.analysis_history = []
                self.notify(f"Sessão criada: {self.session.name}")
            elif action == "abrir":
                session = self.session_repository.load(value)
                if session is None:
                    self.notify("Sessão não encontrada.", severity="warning")
                    return
                self.session = session
                self.analysis_history = [
                    AnalysisRecord(item.number or index + 1, item.created_at, item.prompt, item.result, item.model)
                    for index, item in enumerate(session.analyses)
                ]
                self.notify(f"Sessão aberta: {session.name}")
            else:
                self.notify("Use /sessao nova nome ou /sessao abrir id", severity="warning")
                return
        elif name == "configurar":
            self._open_configurator()
            return
        elif name == "model":
            model = None if argument.lower() == "clear" else argument or None
            if model is None and argument.lower() != "clear":
                self.notify("Use /model nome-do-modelo ou /model clear", severity="warning")
                return
            self.config = AppConfig(
                adb_path=self.config.adb_path,
                serial=self.config.serial,
                max_buffer_lines=self.config.max_buffer_lines,
                codex_model=model,
            )
            self.analyzer.model = model
            save_config(self.config, self.config_path)
            self.notify(f"Modelo Codex: {model or 'padrão'}")
        elif name == "find":
            self.filters.search_query = None if argument.lower() == "clear" else argument or None
        elif name == "regex":
            error = self.filters.set_regex(None if argument.lower() == "clear" else argument)
            if error:
                self.notify(error, severity="error")
                return
        elif name == "clear":
            if argument not in {"", "confirm"}:
                self.notify("Use /clear para limpar somente o buffer local", severity="warning")
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
            self.config = AppConfig(
                adb_path=self.config.adb_path,
                serial=argument or None,
                max_buffer_lines=self.config.max_buffer_lines,
                codex_model=self.config.codex_model,
            )
            if hasattr(self.stream, "client"):
                self.stream.client.serial = self.config.serial
                self.stream.restart()
            else:
                self.stream.restart(serial=self.config.serial)
        elif name == "config" and argument.startswith("adb "):
            self.config = AppConfig(
                adb_path=argument[4:].strip(),
                serial=self.config.serial,
                max_buffer_lines=self.config.max_buffer_lines,
                codex_model=self.config.codex_model,
            )
            save_config(self.config, self.config_path)
        elif name == "config" and argument == "show":
            self.notify(
                f"ADB: {self.config.adb_path or 'adb'} | serial: {self.config.serial or 'auto'} | "
                f"modelo: {self.config.codex_model or 'padrão'}"
            )
        elif name == "save":
            self._save_visible(argument)
        elif name in {"quit", "exit"}:
            self.exit()
        elif name == "help":
            self.showing_help = True
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
        self.last_manual_scroll_at = None
        self.query_one("#log-view", RichLog).scroll_end(animate=False)
