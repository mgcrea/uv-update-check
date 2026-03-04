from __future__ import annotations

import io
from types import SimpleNamespace

from rich.console import Console

from uv_update_check.display import (
    NcuBarColumn,
    _color_for_change,
    _colorize_new_spec,
    _split_spec,
    display_results,
)
from uv_update_check.models import ChangeType

# --- _color_for_change ---


class TestColorForChange:
    def test_major(self):
        assert _color_for_change(ChangeType.MAJOR) == "red"

    def test_minor(self):
        assert _color_for_change(ChangeType.MINOR) == "cyan"

    def test_patch(self):
        assert _color_for_change(ChangeType.PATCH) == "green"

    def test_none(self):
        assert _color_for_change(ChangeType.NONE) == "dim"


# --- _split_spec ---


class TestSplitSpec:
    def test_gte(self):
        assert _split_spec(">=1.0.0") == (">=", "1.0.0")

    def test_caret(self):
        assert _split_spec("^1.0.0") == ("^", "1.0.0")

    def test_bare(self):
        assert _split_spec("1.0.0") == ("", "1.0.0")

    def test_double_equals(self):
        assert _split_spec("==1.0.0") == ("==", "1.0.0")

    def test_tilde_equals(self):
        assert _split_spec("~=1.0.0") == ("~=", "1.0.0")

    def test_lte(self):
        assert _split_spec("<=1.0.0") == ("<=", "1.0.0")

    def test_ne(self):
        assert _split_spec("!=1.0.0") == ("!=", "1.0.0")

    def test_gt(self):
        assert _split_spec(">1.0.0") == (">", "1.0.0")

    def test_lt(self):
        assert _split_spec("<1.0.0") == ("<", "1.0.0")

    def test_gte_before_gt(self):
        """Longer operators must match before shorter ones."""
        op, ver = _split_spec(">=1.0.0")
        assert op == ">="
        assert ver == "1.0.0"


# --- _colorize_new_spec ---


class TestColorizeNewSpec:
    def test_major_change(self):
        text = _colorize_new_spec("1.0.0", "2.0.0", "red")
        # All parts differ from first position onward
        assert text.plain == "2.0.0"

    def test_minor_change(self):
        text = _colorize_new_spec("1.0.0", "1.1.0", "cyan")
        assert text.plain == "1.1.0"

    def test_patch_change(self):
        text = _colorize_new_spec("1.0.0", "1.0.1", "green")
        assert text.plain == "1.0.1"

    def test_with_operator(self):
        text = _colorize_new_spec(">=1.0.0", ">=2.0.0", "red")
        assert text.plain == ">=2.0.0"

    def test_same_version(self):
        text = _colorize_new_spec("1.0.0", "1.0.0", "dim")
        assert text.plain == "1.0.0"


# --- NcuBarColumn ---


class TestNcuBarColumn:
    def _render(self, completed, total, width=20):
        col = NcuBarColumn(width=width)
        task = SimpleNamespace(completed=completed, total=total)
        return col.render(task).plain

    def test_zero_progress(self):
        assert self._render(0, 10) == "[" + " " * 20 + "]"

    def test_half_progress(self):
        assert self._render(5, 10) == "[" + "=" * 10 + " " * 10 + "]"

    def test_full_progress(self):
        assert self._render(10, 10) == "[" + "=" * 20 + "]"

    def test_custom_width(self):
        assert self._render(10, 10, width=10) == "[" + "=" * 10 + "]"


# --- display_results ---


def _captured_console():
    buf = io.StringIO()
    return Console(file=buf, no_color=True, width=120), buf


class TestDisplayResults:
    def test_all_up_to_date(self, make_update_result):
        console, buf = _captured_console()
        results = [make_update_result(change_type=ChangeType.NONE, new_specifier=">=1.0.0", latest_version="1.0.0")]
        display_results(results, "pyproject.toml", console=console)
        assert "All dependencies match the latest package versions" in buf.getvalue()

    def test_one_outdated(self, make_update_result):
        console, buf = _captured_console()
        results = [make_update_result(name="requests", current_version="2.28", new_specifier=">=3.0.0")]
        display_results(results, "pyproject.toml", console=console)
        output = buf.getvalue()
        assert "requests" in output
        assert "3.0.0" in output

    def test_update_mode_message(self, make_update_result):
        console, buf = _captured_console()
        results = [make_update_result()]
        display_results(results, "pyproject.toml", is_update=True, console=console)
        assert "pyproject.toml upgraded" in buf.getvalue()

    def test_check_mode_message(self, make_update_result):
        console, buf = _captured_console()
        results = [make_update_result()]
        display_results(results, "pyproject.toml", is_update=False, console=console)
        assert "uuc -u" in buf.getvalue()

    def test_skipped_excluded(self, make_update_result):
        console, buf = _captured_console()
        results = [make_update_result(name="skipped-pkg", skipped=True)]
        display_results(results, "pyproject.toml", console=console)
        assert "skipped-pkg" not in buf.getvalue()
        assert "All dependencies match" in buf.getvalue()

    def test_error_excluded(self, make_update_result):
        console, buf = _captured_console()
        results = [make_update_result(name="error-pkg", change_type=ChangeType.NONE, error="Failed")]
        display_results(results, "pyproject.toml", console=console)
        assert "error-pkg" not in buf.getvalue()

    def test_arrow_present(self, make_update_result):
        console, buf = _captured_console()
        results = [make_update_result()]
        display_results(results, "pyproject.toml", console=console)
        assert "\u2192" in buf.getvalue()

    def test_multiple_outdated(self, make_update_result):
        console, buf = _captured_console()
        results = [
            make_update_result(name="pkg-a", current_version="1.0", new_specifier=">=2.0"),
            make_update_result(name="pkg-b", current_version="3.0", new_specifier=">=4.0"),
        ]
        display_results(results, "pyproject.toml", console=console)
        output = buf.getvalue()
        assert "pkg-a" in output
        assert "pkg-b" in output
