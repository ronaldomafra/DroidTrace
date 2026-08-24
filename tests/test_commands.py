from __future__ import annotations

import pytest

from logcat_manager.commands import Command, CommandError, parse_command


@pytest.mark.parametrize(
    ("text", "name", "args"),
    [
        (":help", "help", ()),
        (":level E", "level", ("E",)),
        (":level all", "level", ("all",)),
        (":tag Network", "tag", ("Network",)),
        (":pid 123", "pid", (123,)),
        ("/package br.com.tbs.afv.multiplatform", "package", ("br.com.tbs.afv.multiplatform",)),
        ("/analise priorize erros de rede", "analise", ("priorize erros de rede",)),
        ("/model gpt-5.4", "model", ("gpt-5.4",)),
        ("/analises", "analises", ()),
        ("/ver 1", "ver", (1,)),
        ("/logs", "logs", ()),
        (":find fatal exception", "find", ("fatal exception",)),
        (":regex timeout.*", "regex", ("timeout.*",)),
        (":pause", "pause", ()),
        (":resume", "resume", ()),
        (":follow", "follow", ()),
        (":restart", "restart", ()),
        (":device emulator-5554", "device", ("emulator-5554",)),
        (":config show", "config", ("show",)),
        (":config adb C:/SDK/adb.exe", "config", ("adb", "C:/SDK/adb.exe")),
        (":save \"C:/logs/my log.txt\"", "save", ("C:/logs/my log.txt",)),
        (":quit", "quit", ()),
    ],
)
def test_parser_creates_supported_commands(text, name, args):
    assert parse_command(text) == Command(name, args)


def test_plain_text_becomes_quick_find():
    assert parse_command("fatal exception") == Command("find", ("fatal exception",))


@pytest.mark.parametrize("text", [":clear", ":adb-clear"])
def test_destructive_commands_reject_missing_literal_confirmation(text):
    with pytest.raises(CommandError, match="confirm"):
        parse_command(text)


@pytest.mark.parametrize("text, name", [(":clear confirm", "clear"), (":adb-clear confirm", "adb-clear")])
def test_destructive_commands_accept_only_confirm_token(text, name):
    assert parse_command(text) == Command(name, (), confirmed=True)


@pytest.mark.parametrize("text", [":level X", ":pid nope", ":unknown", ":clear CONFIRM"])
def test_invalid_commands_raise_friendly_error(text):
    with pytest.raises(CommandError):
        parse_command(text)
