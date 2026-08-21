from __future__ import annotations

import argparse
from pathlib import Path

from .config import AppConfig, load_config, resolve_adb_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Interactive colored Android logcat viewer")
    parser.add_argument("--adb-path", help="Path to adb executable")
    parser.add_argument("--serial", help="ADB device serial")
    parser.add_argument("--config", type=Path, help="Path to configuration JSON")
    parser.add_argument("--max-buffer-lines", type=int, help="Maximum local log entries")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    config = load_config(args.config)
    adb_path = resolve_adb_path(args.adb_path, config)
    effective = AppConfig(
        adb_path=adb_path,
        serial=args.serial or config.serial,
        max_buffer_lines=args.max_buffer_lines or config.max_buffer_lines,
    )
    from .app import LogcatApp

    LogcatApp(config=effective, config_path=args.config).run()


if __name__ == "__main__":
    main()
