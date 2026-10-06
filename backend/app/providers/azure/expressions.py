"""ARM template expressions the platform evaluates itself: uniqueString and the names built from it."""

import re
from collections.abc import Callable

MASK_32 = 0xFFFFFFFF
MASK_64 = 0xFFFFFFFFFFFFFFFF
BASE32 = "abcdefghijklmnopqrstuvwxyz234567"
UNIQUE_LENGTH = 13
TOKEN = re.compile(r"\s*(?:(?P<string>'(?:[^']|'')*')|(?P<number>-?\d+)|(?P<name>[A-Za-z_][A-Za-z0-9_]*)|(?P<symbol>[(),.]))")
END = ("end", "")


def _rotate(value: int, bits: int) -> int:
    return ((value << bits) | (value >> (32 - bits))) & MASK_32


def _mix(value: int) -> int:
    value ^= value >> 16
    value = (value * 0x85EBCA6B) & MASK_32
    value ^= value >> 13
    value = (value * 0xC2B2AE35) & MASK_32
    return value ^ (value >> 16)


def _murmur64(data: bytes) -> int:
    """The 64-bit MurmurHash variant Azure Resource Manager uses (seed 0)."""
    c1, c2 = 0x239B961B, 0xAB0E9789
    h1 = h2 = 0
    full = len(data) - len(data) % 8
    for index in range(0, full, 8):
        k1 = (_rotate((int.from_bytes(data[index:index + 4], "little") * c1) & MASK_32, 15) * c2) & MASK_32
        h1 = (_rotate(h1 ^ k1, 19) + h2) & MASK_32
        h1 = (h1 * 5 + 0x561CCD1B) & MASK_32
        k2 = (_rotate((int.from_bytes(data[index + 4:index + 8], "little") * c2) & MASK_32, 17) * c1) & MASK_32
        h2 = (_rotate(h2 ^ k2, 13) + h1) & MASK_32
        h2 = (h2 * 5 + 0x0BCAA747) & MASK_32
    tail = data[full:]
    if tail:
        h1 ^= (_rotate((int.from_bytes(tail[:4], "little") * c1) & MASK_32, 15) * c2) & MASK_32
    if len(tail) > 4:
        h2 ^= (_rotate((int.from_bytes(tail[4:], "little") * c2) & MASK_32, 17) * c1) & MASK_32
    h1, h2 = h1 ^ len(data), h2 ^ len(data)
    h1 = (h1 + h2) & MASK_32
    h2 = (h2 + h1) & MASK_32
    h1, h2 = _mix(h1), _mix(h2)
    h1 = (h1 + h2) & MASK_32
    h2 = (h2 + h1) & MASK_32
    return (h2 << 32) | h1


def unique_string(*parts: str) -> str:
    """ARM's `uniqueString(...)`: the parts joined with '-', hashed, and the hash's 64 bits as 13 base-32 letters."""
    value, letters = _murmur64("-".join(parts).encode()), []
    for _ in range(UNIQUE_LENGTH):
        letters.append(BASE32[value >> 59])
        value = (value << 5) & MASK_64
    return "".join(letters)


class Unresolvable(Exception):
    """The expression uses something the platform cannot know before deployment."""


class ArmExpressions:
    """Evaluates the name expressions the templates use, for one environment's resource group. Anything else (a
    function it does not know, a parameter or variable it is not given) makes the value unknown: `None`."""

    def __init__(self, parameters: dict[str, str], variables: dict[str, object], resource_group_id: str):
        self._parameters = parameters
        self._variables = variables
        self._functions: dict[str, Callable[..., object]] = {
            "concat": self._concat, "take": self._take, "uniqueString": self._unique, "format": self._format,
            "toLower": lambda text: self._text(text).lower(), "parameters": self._parameter,
            "variables": self._variable, "resourceGroup": lambda: {"id": resource_group_id}}

    def evaluate(self, text) -> str | None:
        try:
            value = self._value(text)
        except Unresolvable:
            return None
        return value if isinstance(value, str) else None

    def _value(self, text) -> object:
        if not isinstance(text, str):
            raise Unresolvable
        if text.startswith("[["):
            return text[1:]
        if not (text.startswith("[") and text.endswith("]")):
            return text
        tokens = self._tokens(text[1:-1])
        value, position = self._expression(tokens, 0)
        if tokens[position] != END:
            raise Unresolvable
        return value

    @staticmethod
    def _tokens(body: str) -> list[tuple[str, str]]:
        tokens, position = [], 0
        while position < len(body.rstrip()):
            match = TOKEN.match(body, position)
            if match is None:
                raise Unresolvable
            tokens.append((match.lastgroup, match[match.lastgroup]))
            position = match.end()
        return [*tokens, END]

    def _expression(self, tokens: list, position: int) -> tuple[object, int]:
        kind, token = tokens[position]
        if kind == "end":
            raise Unresolvable
        if kind == "string":
            return token[1:-1].replace("''", "'"), position + 1
        if kind == "number":
            return int(token), position + 1
        if kind != "name" or token not in self._functions or tokens[position + 1] != ("symbol", "("):
            raise Unresolvable
        arguments, position = [], position + 2
        while tokens[position] != ("symbol", ")"):
            if tokens[position] == END:
                raise Unresolvable
            argument, position = self._expression(tokens, position)
            arguments.append(argument)
            if tokens[position] == ("symbol", ","):
                position += 1
        value, position = self._functions[token](*arguments), position + 1
        while tokens[position] == ("symbol", ".") and tokens[position + 1][0] == "name":
            value, position = self._property(value, tokens[position + 1][1]), position + 2
        return value, position

    @staticmethod
    def _property(value: object, name: str) -> object:
        if not isinstance(value, dict) or name not in value:
            raise Unresolvable
        return value[name]

    @staticmethod
    def _text(value: object) -> str:
        if not isinstance(value, str):
            raise Unresolvable
        return value

    def _concat(self, *values) -> str:
        return "".join(self._text(value) for value in values)

    def _take(self, value, count) -> str:
        if not isinstance(count, int):
            raise Unresolvable
        return self._text(value)[:count]

    def _unique(self, *values) -> str:
        return unique_string(*(self._text(value) for value in values))

    def _format(self, template, *values) -> str:
        return self._text(template).format(*(self._text(value) for value in values))

    def _parameter(self, name) -> str:
        if name not in self._parameters:
            raise Unresolvable
        return self._parameters[name]

    def _variable(self, name) -> object:
        if name not in self._variables:
            raise Unresolvable
        return self._value(self._variables[name])
