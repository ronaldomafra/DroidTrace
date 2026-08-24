from __future__ import annotations

import json
import os
import shutil
import urllib.request
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


class HttpProviderAnalyzer:
    def __init__(self, settings: ProviderSettings) -> None:
        self.provider = settings.provider
        self.model = settings.model or available_models(settings.provider)[0]

    def analyze(self, entries, user_prompt: str = "") -> str:
        from .analysis import CodexAnalyzer

        key_name = ENV_KEYS[self.provider]
        api_key = os.environ[key_name]
        prompt = CodexAnalyzer._build_prompt([entry.raw for entry in entries][-250:], user_prompt)
        if self.provider == "claude":
            url = "https://api.anthropic.com/v1/messages"
            headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
            payload = {"model": self.model, "max_tokens": 1200, "messages": [{"role": "user", "content": prompt}]}
        else:
            url = "https://api.moonshot.cn/v1/chat/completions" if self.provider == "kimi" else "https://openrouter.ai/api/v1/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}", "content-type": "application/json"}
            payload = {"model": self.model, "messages": [{"role": "user", "content": prompt}]}
        request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(request, timeout=120) as response:
            data = json.loads(response.read().decode("utf-8"))
        if self.provider == "claude":
            return data["content"][0]["text"]
        return data["choices"][0]["message"]["content"]


def create_analyzer(settings: ProviderSettings):
    if settings.provider == "codex":
        from .analysis import CodexAnalyzer
        return CodexAnalyzer(model=settings.model)
    return HttpProviderAnalyzer(settings)
