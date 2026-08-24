from __future__ import annotations

import os

from droidtrace.providers import ProviderSettings, available_models, validate_provider


def test_codex_needs_local_cli_but_no_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    assert validate_provider(ProviderSettings(provider="codex", model="gpt-5.4"), which=lambda _: "codex") is None


def test_http_providers_require_their_environment_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    error = validate_provider(ProviderSettings(provider="openrouter", model="openai/gpt-4.1"))

    assert "OPENROUTER_API_KEY" in error


def test_provider_models_include_custom_choice():
    models = available_models("kimi")

    assert "Custom" in models
    assert models[0].startswith("moonshot")
