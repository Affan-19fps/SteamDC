from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any


def parse_vdf(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    tokens = _tokenize(lines)
    parser = _Parser(tokens)
    result = parser.parse()
    return result


def _tokenize(lines: list[str]) -> list[str]:
    tokens = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue
        idx = 0
        while idx < len(stripped):
            if stripped[idx] in "{}":
                tokens.append(stripped[idx])
                idx += 1
            elif stripped[idx] == '"':
                end = idx + 1
                while end < len(stripped):
                    if stripped[end] == '"' and stripped[end - 1 : end] != "\\":
                        break
                    end += 1
                tokens.append(stripped[idx : end + 1])
                idx = end + 1
            elif stripped[idx] in " \t":
                idx += 1
            else:
                end = idx
                while end < len(stripped) and stripped[end] not in "{} \t":
                    end += 1
                tokens.append(stripped[idx:end])
                idx = end
    return tokens


class _Parser:
    def __init__(self, tokens: list[str]):
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> str | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def consume(self, expected: str | None = None) -> str:
        token = self.peek()
        if token is None:
            raise ValueError("Unexpected end of input")
        if expected is not None and token != expected:
            raise ValueError(f"Expected {expected!r}, got {token!r}")
        self.pos += 1
        return token

    def parse(self) -> dict[str, Any]:
        node = {}
        key = self._parse_key()
        val = self._parse_value()
        node[key] = val
        remaining = self.peek()
        if remaining is not None and remaining != "}":
            next_key = self._parse_key()
            next_val = self._parse_value()
            if isinstance(node[key], dict):
                node[key][next_key] = next_val
            else:
                node = {key: node[key], next_key: next_val}
            while self.peek() is not None and self.peek() != "}":
                k = self._parse_key()
                v = self._parse_value()
                node[k] = v
        return node

    def _parse_key(self) -> str:
        token = self.consume()
        return token.strip('"')

    def _parse_value(self) -> Any:
        token = self.peek()
        if token == "{":
            return self._parse_object()
        else:
            return self.consume().strip('"')

    def _parse_object(self) -> dict[str, Any]:
        self.consume("{")
        obj = {}
        while self.peek() is not None and self.peek() != "}":
            key = self._parse_key()
            value = self._parse_value()
            obj[key] = value
        self.consume("}")
        return obj


def load_acf(path: str | Path) -> dict[str, Any]:
    text = Path(path).read_text(encoding="utf-8")
    return parse_vdf(text)


def save_acf(data: dict[str, Any], path: str | Path) -> None:
    lines = _serialize(data)
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _serialize(data: Any, indent: int = 0) -> list[str]:
    pad = "\t" * indent
    if isinstance(data, dict):
        items = list(data.items())
        if not items:
            return [f"{pad}\n" + "{" + "\n" + pad + "}"]
        lines = []
        for key, val in items:
            if isinstance(val, dict):
                lines.append(f"{pad}\t\"{key}\"")
                lines.append(f"{pad}\t" + "{")
                lines.extend(_serialize(val, indent + 2))
                lines.append(f"{pad}\t" + "}")
            else:
                lines.append(f"{pad}\t\"{key}\"\t\t\"{val}\"")
        return lines
    return [f"{pad}\"{data}\""]
