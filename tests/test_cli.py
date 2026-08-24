from __future__ import annotations


def test_parse_args_accepts_adb_options():
    from droidtrace.__main__ import parse_args

    args = parse_args([
        "--adb-path", "C:/sdk/adb.exe", "--serial", "emulator-5554", "--max-buffer-lines", "321",
        "--codex-model", "gpt-5.4",
    ])

    assert args.adb_path == "C:/sdk/adb.exe"
    assert args.serial == "emulator-5554"
    assert args.max_buffer_lines == 321
    assert args.codex_model == "gpt-5.4"
