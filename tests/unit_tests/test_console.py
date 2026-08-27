import io
from typing import TextIO, cast

from angel.console import BOLD, CYAN, RESET, color_enabled, section, style


class TtyStream(io.StringIO):
    def isatty(self) -> bool:
        return True


def _clear_color_env(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("ANGEL_COLOR", raising=False)


def test_color_enabled_false_for_non_tty_stream(monkeypatch):
    _clear_color_env(monkeypatch)
    assert color_enabled(io.StringIO()) is False


def test_color_enabled_true_for_tty_stream(monkeypatch):
    _clear_color_env(monkeypatch)
    assert color_enabled(TtyStream()) is True


def test_no_color_forces_false_for_tty_stream(monkeypatch):
    _clear_color_env(monkeypatch)
    monkeypatch.setenv("NO_COLOR", "1")
    assert color_enabled(TtyStream()) is False


def test_angel_color_always_forces_true_for_non_tty(monkeypatch):
    _clear_color_env(monkeypatch)
    monkeypatch.setenv("ANGEL_COLOR", "always")
    assert color_enabled(io.StringIO()) is True


def test_angel_color_never_forces_false_for_tty(monkeypatch):
    _clear_color_env(monkeypatch)
    monkeypatch.setenv("ANGEL_COLOR", "never")
    assert color_enabled(TtyStream()) is False


def test_angel_color_auto_defers_to_isatty(monkeypatch):
    _clear_color_env(monkeypatch)
    monkeypatch.setenv("ANGEL_COLOR", "auto")
    assert color_enabled(TtyStream()) is True
    assert color_enabled(io.StringIO()) is False


def test_angel_color_unrecognised_value_defers_to_isatty(monkeypatch):
    _clear_color_env(monkeypatch)
    monkeypatch.setenv("ANGEL_COLOR", "bogus")
    assert color_enabled(TtyStream()) is True
    assert color_enabled(io.StringIO()) is False


def test_color_enabled_handles_stream_without_isatty(monkeypatch):
    _clear_color_env(monkeypatch)

    class NoIsatty:
        pass

    assert color_enabled(cast(TextIO, NoIsatty())) is False


def test_style_returns_text_unchanged_when_color_disabled(monkeypatch):
    _clear_color_env(monkeypatch)
    stream = io.StringIO()
    assert style("hello", BOLD, stream=stream) == "hello"


def test_style_returns_text_unchanged_when_no_codes(monkeypatch):
    _clear_color_env(monkeypatch)
    stream = TtyStream()
    assert style("hello", stream=stream) == "hello"


def test_style_wraps_text_when_color_enabled(monkeypatch):
    _clear_color_env(monkeypatch)
    stream = TtyStream()
    assert style("hello", BOLD, CYAN, stream=stream) == "\x1b[1;36mhello\x1b[0m"


def test_section_writes_heading_with_title(monkeypatch):
    _clear_color_env(monkeypatch)
    stream = io.StringIO()
    section("Reviews", stream=stream)
    output = stream.getvalue()
    assert "Reviews" in output
    assert "\x1b" not in output


def test_section_styles_heading_when_color_enabled(monkeypatch):
    _clear_color_env(monkeypatch)
    stream = TtyStream()
    section("Reviews", stream=stream)
    output = stream.getvalue()
    assert f"\x1b[{BOLD};{CYAN}m" in output
    assert output.rstrip("\n").endswith(f"\x1b[{RESET}m")
