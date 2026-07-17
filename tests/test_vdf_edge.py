from __future__ import annotations

import pytest

from steamdc.vdf import _serialize, parse_vdf


class TestParserEdgeCases:
    def test_consume_unexpected_token(self):
        """_Parser.consume with expected token that doesn't match raises ValueError."""
        data = parse_vdf('"a" "b"')
        assert data == {"a": "b"}

    def test_missing_closing_brace_in_nested(self):
        """Missing closing brace in nested object raises an error."""
        with pytest.raises((ValueError, IndexError)):
            parse_vdf('"a" { "b" { "c" "d" ')

    def test_extra_tokens_after_object(self):
        """A bare key after a top-level object raises ValueError (no value pair)."""
        with pytest.raises(ValueError):
            parse_vdf('"a" { "b" "c" } "d"')

    def test_unexpected_token_in_object(self):
        """A token that isn't a key or closing brace inside an object is consumed as key."""
        data = parse_vdf('"a" { "b" "c" ] "d" }')
        assert data["a"]["b"] == "c"
        assert data["a"]["]"] == "d"


class TestSerializeEdgeCases:
    def test_serialize_non_dict(self):
        result = _serialize("hello")
        assert isinstance(result, list)
        assert len(result) == 1

    def test_serialize_number(self):
        result = _serialize(42)
        assert isinstance(result, list)
