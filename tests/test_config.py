from __future__ import annotations

from droidtrace.config import AppConfig, load_config, resolve_adb_path, save_config


def test_cli_path_has_highest_precedence(monkeypatch):
    monkeypatch.setenv("ADB_PATH", "env-adb")
    config = AppConfig(adb_path="stored-adb")

    assert resolve_adb_path("cli-adb", config, which=lambda _: "path-adb") == "cli-adb"


def test_config_round_trip(tmp_path):
    path = tmp_path / "settings.json"
    expected = AppConfig(
        adb_path="C:/sdk/adb.exe",
        serial="emulator-5554",
        max_buffer_lines=123,
        codex_model="gpt-5.4",
    )

    save_config(expected, path)

    assert load_config(path) == expected


def test_path_fallback_order(monkeypatch):
    monkeypatch.delenv("ADB_PATH", raising=False)
    assert resolve_adb_path(None, AppConfig(adb_path="stored"), which=lambda _: "found") == "stored"
    assert resolve_adb_path(None, AppConfig(), which=lambda _: "found") == "found"
