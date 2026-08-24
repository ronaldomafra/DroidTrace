from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, OptionList, Static
from textual.widgets.option_list import Option

from .providers import ProviderSettings, available_models, validate_provider
from .sessions import SessionRepository


class ConfigScreen(ModalScreen[ProviderSettings | None]):
    """First-run provider/model setup with recent sessions as context."""

    CSS = """
    ConfigScreen { align: center middle; }
    #config-box { width: 76; height: auto; max-height: 90%; border: round $accent; padding: 1 2; }
    #provider-list, #model-list { height: 6; }
    #config-status { color: $warning; height: auto; }
    """

    def __init__(self, current: ProviderSettings, session_directory: Path) -> None:
        super().__init__()
        self.current = current
        self.session_directory = session_directory
        self.selected_provider = current.provider
        self.selected_model = current.model or available_models(current.provider)[0]

    def compose(self) -> ComposeResult:
        recent = SessionRepository(self.session_directory).recent(5)
        with Vertical(id="config-box"):
            yield Static("DROIDTRACE — Configuração inicial")
            yield Static("1. Selecione o provider")
            yield OptionList(*(Option(name, id=name) for name in ("codex", "claude", "kimi", "openrouter")), id="provider-list")
            yield Static("2. Selecione o modelo")
            yield OptionList(*self._model_options(), id="model-list")
            yield Static("Sessões recentes: " + (", ".join(session.name for session in recent) or "nenhuma"))
            yield Static("", id="config-status")
            yield Button("Salvar", id="save-config", variant="success")
            yield Button("Cancelar", id="cancel-config")

    def _model_options(self) -> list[Option]:
        return [Option(model, id=model) for model in available_models(self.selected_provider)]

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_id is None:
            return
        if event.option_list.id == "provider-list":
            self.selected_provider = event.option_id
            self.selected_model = available_models(self.selected_provider)[0]
            self.query_one("#model-list", OptionList).set_options(self._model_options())
        elif event.option_list.id == "model-list":
            self.selected_model = event.option_id

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-config":
            self.dismiss(None)
            return
        settings = ProviderSettings(self.selected_provider, self.selected_model)
        error = validate_provider(settings)
        if error:
            self.query_one("#config-status", Static).update(error)
            return
        self.dismiss(settings)
