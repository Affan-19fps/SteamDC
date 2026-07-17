from pathlib import Path

import pytest

from steamdc.vdf import parse_vdf, load_acf, save_acf, _serialize


SAMPLE_ACF = '''"AppState"
{
\t"appid"\t\t"240"
\t"universe"\t\t"1"
\t"name"\t\t"Counter-Strike: Source"
\t"StateFlags"\t\t"4"
\t"installdir"\t\t"Counter-Strike Source"
\t"LastUpdated"\t\t"1776007826"
\t"SizeOnDisk"\t\t"4880436674"
\t"BytesToDownload"\t\t"2716461696"
\t"BytesDownloaded"\t\t"2716461696"
\t"InstalledDepots"
\t{
\t\t"241"
\t\t{
\t\t\t"manifest"\t\t"6941588918651947824"
\t\t\t"size"\t\t"4558841879"
\t\t}
\t}
\t"UserConfig"
\t{
\t\t"language"\t\t"english"
\t}
}
'''

SAMPLE_LIBRARY_VDF = '''"libraryfolders"
{
\t"0"
\t{
\t\t"path"\t\t"C:\\\\Program Files (x86)\\\\Steam"
\t}
\t"1"
\t{
\t\t"path"\t\t"D:\\\\SteamLibrary"
\t}
}
'''


class TestTokenize:
    def test_line_with_only_braces(self):
        data = parse_vdf('"a" { }')
        assert data == {"a": {}}

    def test_extra_whitespace(self):
        data = parse_vdf('  "a"   "b"  ')
        assert data == {"a": "b"}


class TestVDFParser:
    def test_parse_simple_key_value(self):
        data = parse_vdf('"key" "value"')
        assert data == {"key": "value"}

    def test_parse_nested_object(self):
        data = parse_vdf('"obj" { "inner" "val" }')
        assert data == {"obj": {"inner": "val"}}

    def test_parse_acf_format(self):
        data = parse_vdf(SAMPLE_ACF)
        app = data.get("AppState", {})
        assert app["appid"] == "240"
        assert app["name"] == "Counter-Strike: Source"
        assert app["StateFlags"] == "4"
        assert app["BytesToDownload"] == "2716461696"
        assert app["BytesDownloaded"] == "2716461696"

    def test_parse_installed_depots(self):
        data = parse_vdf(SAMPLE_ACF)
        depots = data["AppState"]["InstalledDepots"]
        assert "241" in depots
        assert depots["241"]["manifest"] == "6941588918651947824"
        assert depots["241"]["size"] == "4558841879"

    def test_parse_library_folders(self):
        data = parse_vdf(SAMPLE_LIBRARY_VDF)
        libs = data.get("libraryfolders", {})
        assert "0" in libs
        assert libs["0"]["path"] == "C:\\\\Program Files (x86)\\\\Steam"
        assert libs["1"]["path"] == "D:\\\\SteamLibrary"

    def test_parse_empty_object(self):
        data = parse_vdf('"empty" { }')
        assert data == {"empty": {}}

    def test_parse_with_comments(self):
        vdf = '// this is a comment\n"key" "value"'
        data = parse_vdf(vdf)
        assert data == {"key": "value"}

    def test_parse_multiple_top_level_keys(self):
        vdf = '"a" "1"\n"b" "2"'
        data = parse_vdf(vdf)
        assert data == {"a": "1", "b": "2"}

    def test_parse_empty_input(self):
        with pytest.raises((ValueError, IndexError, KeyError)):
            parse_vdf("")

    def test_parse_missing_closing_brace(self):
        with pytest.raises((ValueError, IndexError)):
            parse_vdf('"a" { "b" "c" ')


class TestACFSerialization:
    def test_roundtrip(self):
        original = parse_vdf(SAMPLE_ACF)
        serialized = "\n".join(_serialize(original))
        reparsed = parse_vdf(serialized)
        assert original == reparsed

    def test_serialize_empty_dict(self):
        result = _serialize({})
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_save_and_load_roundtrip(self, tmp_path: Path):
        original = parse_vdf(SAMPLE_ACF)
        path = tmp_path / "test.acf"
        save_acf(original, path)
        assert path.exists()
        reloaded = load_acf(path)
        assert original == reloaded


class TestLoadACF:
    def test_load_from_file(self, tmp_path: Path):
        acf_file = tmp_path / "appmanifest_240.acf"
        acf_file.write_text(SAMPLE_ACF, encoding="utf-8")
        data = load_acf(acf_file)
        assert data["AppState"]["name"] == "Counter-Strike: Source"

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_acf("nonexistent.acf")
