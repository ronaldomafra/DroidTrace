from __future__ import annotations

import shlex
from dataclasses import dataclass


class CommandError(ValueError):
    """Raised when prompt text is not a valid command."""


@dataclass(frozen=True)
class Command:
    name: str
    args: tuple[object, ...] = ()
    confirmed: bool = False


_NO_ARGUMENT = {"help", "pause", "resume", "follow", "restart", "quit", "analises", "logs"}
_CLEARABLE = {"tag", "pid", "find", "regex"}


def parse_command(text: str) -> Command:
    text = text.strip()
    if not text:
        raise CommandError("command cannot be empty")
    if text.startswith("/"):
        text = ":" + text[1:]
    if not text.startswith(":"):
        return Command("find", (text,))

    try:
        parts = shlex.split(text[1:])
    except ValueError as error:
        raise CommandError(f"invalid command syntax: {error}") from error
    if not parts:
        raise CommandError("command cannot be empty")

    name, *arguments = parts
    if name in _NO_ARGUMENT:
        _require_count(name, arguments, 0)
        return Command(name)
    if name == "clear":
        _require_count(name, arguments, 0)
        return Command(name)
    if name == "adb-clear":
        if arguments != ["confirm"]:
            raise CommandError(f":{name} requires the literal token confirm")
        return Command(name, confirmed=True)
    if name == "level":
        _require_count(name, arguments, 1)
        level = arguments[0].upper()
        if level not in {"V", "D", "I", "W", "E", "F", "ALL"}:
            raise CommandError("level must be V, D, I, W, E, F, or all")
        return Command(name, (level.lower() if level == "ALL" else level,))
    if name in _CLEARABLE:
        _require_count(name, arguments, 1, allow_many=name in {"find", "regex"})
        if arguments == ["clear"]:
            return Command(name, ("clear",))
        if name == "pid":
            try:
                return Command(name, (int(arguments[0]),))
            except ValueError as error:
                raise CommandError("pid must be a number or clear") from error
        value = " ".join(arguments) if name in {"find", "regex"} else arguments[0]
        return Command(name, (value,))
    if name == "package":
        _require_count(name, arguments, 1)
        return Command(name, (arguments[0],))
    if name == "analise":
        return Command(name, (" ".join(arguments),))
    if name == "model":
        _require_count(name, arguments, 1)
        return Command(name, (arguments[0],))
    if name == "ver":
        _require_count(name, arguments, 1)
        try:
            return Command(name, (int(arguments[0]),))
        except ValueError as error:
            raise CommandError("ver expects an analysis number") from error
    if name == "device":
        _require_count(name, arguments, 1)
        return Command(name, (arguments[0],))
    if name == "config":
        if arguments == ["show"]:
            return Command(name, ("show",))
        if len(arguments) == 2 and arguments[0] == "adb":
            return Command(name, ("adb", arguments[1]))
        raise CommandError("config expects show or adb <path>")
    if name == "save":
        _require_count(name, arguments, 1)
        return Command(name, (arguments[0],))
    raise CommandError(f"unknown command: :{name}")


def _require_count(name: str, arguments: list[str], count: int, *, allow_many: bool = False) -> None:
    valid = len(arguments) >= count if allow_many else len(arguments) == count
    if not valid:
        raise CommandError(f":{name} expects {'at least ' if allow_many else ''}{count} argument(s)")
