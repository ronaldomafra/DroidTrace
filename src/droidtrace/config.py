from __future__ import annotations

import json
import os
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

WINDOWS_ADB_DEFAULT = Path("C:/Android/android-studio-sdk/platform-tools/adb.exe")


@dataclass(frozen=True)
class AppConfig:
    adb_path: str | None = None
    serial: str | None = None
    max_buffer_lines: int = 10_000
    codex_model: str | None = None
    provider: str = "codex"
    session_dir: str | None = None
    recording_dir: str | None = None


def default_config_path() -> Path:
    root = Path(os.environ.get("APPDATA", Path.home() / ".config"))
    return root / "droidtrace" / "config.json"


def load_config(path: Path | None = None) -> AppConfig:
    target = path or default_config_path()
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return AppConfig()
    return AppConfig(
        adb_path=data.get("adb_path"),
        serial=data.get("serial"),
        max_buffer_lines=int(data.get("max_buffer_lines", 10_000)),
        codex_model=data.get("codex_model"),
        provider=data.get("provider", "codex"),
        session_dir=data.get("session_dir"),
        recording_dir=data.get("recording_dir"),
    )


def save_config(config: AppConfig, path: Path | None = None) -> Path:
    target = path or default_config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(asdict(config), indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
    return target


def resolve_adb_path(
    cli_path: str | None,
    config: AppConfig,
    *,
    which: Callable[[str], str | None] = shutil.which,
) -> str:
    if cli_path:
        return cli_path
    if env_path := os.environ.get("ADB_PATH"):
        return env_path
    if config.adb_path:
        return config.adb_path
    if found := which("adb"):
        return found
    return str(WINDOWS_ADB_DEFAULT)
