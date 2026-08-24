from __future__ import annotations

import os
import shutil
from dataclasses import dataclass


MODEL_CATALOG = {
    "codex": ("gpt-5.4", "gpt-5.3-codex", "Custom"),
    "claude": ("claude-sonnet-4-5", "claude-opus-4-5", "Custom"),
    "kimi": ("moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k", "Custom"),
    "openrouter": ("openai/gpt-4.1", "anthropic/claude-sonnet-4", "google/gemini-2.5-pro", "Custom"),
}
ENV_KEYS = {
    "claude": "ANTHROPIC_API_KEY",
    "kimi": "KIMI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}


@dataclass(frozen=True)
class ProviderSettings:
    provider: str = "codex"
    model: str | None = None


def available_models(provider: str) -> tuple[str, ...]:
    return MODEL_CATALOG.get(provider.casefold(), ("Custom",))


def validate_provider(settings: ProviderSettings, *, which=shutil.which) -> str | None:
    provider = settings.provider.casefold()
    if provider not in MODEL_CATALOG:
        return f"Provider desconhecido: {settings.provider}"
    if provider == "codex":
        return None if which("codex") else "Codex CLI não encontrado no PATH."
    key = ENV_KEYS[provider]
    return None if os.environ.get(key) else f"Defina a variável de ambiente {key}."
