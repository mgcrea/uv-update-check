from __future__ import annotations

import tomlkit
from packaging.version import Version

from uv_update_check.models import ChangeType, Dependency, DependencySection, UpdateResult
from uv_update_check.updater import (
    _extract_name,
    _format_old_spec,
    _replace_version,
    _update_array,
    apply_updates,
)

# --- helpers ---


def _make_result(
    name="requests",
    operator=">=",
    current_version="2.28",
    new_specifier=">=3.0.0",
    change_type=ChangeType.MAJOR,
    latest_version="3.0.0",
    skipped=False,
    error=None,
):
    dep = Dependency(
        name=name,
        raw_string=f"{name}{operator}{current_version}",
        operator=operator,
        current_version=current_version,
        section=DependencySection.MAIN,
    )
    return UpdateResult(
        dependency=dep,
        latest_version=Version(latest_version) if latest_version else None,
        change_type=change_type,
        new_specifier=new_specifier,
        skipped=skipped,
        error=error,
    )


# --- _extract_name ---


class TestExtractName:
    def test_simple(self):
        assert _extract_name("requests>=2.28") == "requests"

    def test_with_extras(self):
        assert _extract_name("httpx[http2]>=0.27") == "httpx"

    def test_normalized(self):
        assert _extract_name("My_Package>=1.0") == "my-package"

    def test_empty_string(self):
        assert _extract_name("") == ""

    def test_single_char(self):
        assert _extract_name("x>=1.0") == "x"


# --- _format_old_spec ---


class TestFormatOldSpec:
    def test_caret(self):
        assert _format_old_spec("^", "1.0.0") == "^1.0.0"

    def test_gte(self):
        assert _format_old_spec(">=", "1.0.0") == ">=1.0.0"

    def test_bare(self):
        assert _format_old_spec("", "1.0.0") == "1.0.0"

    def test_all_standard_operators(self):
        for op in (">=", "<=", ">", "<", "!=", "~=", "=="):
            assert _format_old_spec(op, "1.0.0") == f"{op}1.0.0"


# --- _replace_version ---


class TestReplaceVersion:
    def test_gte(self):
        result = _make_result(operator=">=", current_version="2.28", new_specifier=">=3.0.0")
        assert _replace_version("requests>=2.28", result) == "requests>=3.0.0"

    def test_caret(self):
        result = _make_result(operator="^", current_version="2.28", new_specifier="^3.0.0")
        assert _replace_version("requests^2.28", result) == "requests^3.0.0"

    def test_preserves_extras_and_marker(self):
        result = _make_result(
            name="httpx",
            operator=">=",
            current_version="0.27",
            new_specifier=">=0.28",
        )
        raw = "httpx[http2]>=0.27 ; python_version>='3.8'"
        assert _replace_version(raw, result) == "httpx[http2]>=0.28 ; python_version>='3.8'"

    def test_no_match_returns_unchanged(self):
        result = _make_result(operator=">=", current_version="9.9.9", new_specifier=">=10.0.0")
        raw = "requests>=2.28"
        assert _replace_version(raw, result) == raw


# --- _update_array ---


class TestUpdateArray:
    def test_single_match(self):
        arr = tomlkit.array()
        arr.append("requests>=2.28")
        arr.append("click>=8.0")
        updatable = {"requests": _make_result()}
        count = _update_array(arr, updatable)
        assert count == 1
        assert ">=3.0.0" in arr[0]
        assert arr[1] == "click>=8.0"

    def test_no_match(self):
        arr = tomlkit.array()
        arr.append("click>=8.0")
        count = _update_array(arr, {"requests": _make_result()})
        assert count == 0

    def test_skips_non_string(self):
        arr = tomlkit.array()
        arr.append({"include-group": "dev"})
        arr.append("requests>=2.28")
        updatable = {"requests": _make_result()}
        count = _update_array(arr, updatable)
        assert count == 1

    def test_multiple_matches(self):
        arr = tomlkit.array()
        arr.append("requests>=2.28")
        arr.append("click>=8.0")
        updatable = {
            "requests": _make_result(name="requests", current_version="2.28", new_specifier=">=3.0.0"),
            "click": _make_result(name="click", current_version="8.0", new_specifier=">=9.0.0"),
        }
        count = _update_array(arr, updatable)
        assert count == 2


# --- apply_updates ---


class TestApplyUpdates:
    def test_writes_file(self, tmp_path):
        p = tmp_path / "pyproject.toml"
        p.write_text('[project]\ndependencies = ["requests>=2.28"]\n')
        doc = tomlkit.parse(p.read_text())
        results = [_make_result()]
        count = apply_updates(p, doc, results)
        assert count == 1
        content = p.read_text()
        assert ">=3.0.0" in content

    def test_preserves_comments(self, tmp_path):
        toml_str = """\
[project]
# Main deps
dependencies = ["requests>=2.28"]  # HTTP library
"""
        p = tmp_path / "pyproject.toml"
        p.write_text(toml_str)
        doc = tomlkit.parse(p.read_text())
        results = [_make_result()]
        apply_updates(p, doc, results)
        content = p.read_text()
        assert "# Main deps" in content
        assert "# HTTP library" in content

    def test_no_updatable_returns_zero(self, tmp_path):
        p = tmp_path / "pyproject.toml"
        original = '[project]\ndependencies = ["requests>=2.28"]\n'
        p.write_text(original)
        doc = tomlkit.parse(p.read_text())
        result = _make_result(change_type=ChangeType.NONE)
        count = apply_updates(p, doc, [result])
        assert count == 0

    def test_skipped_not_applied(self, tmp_path):
        p = tmp_path / "pyproject.toml"
        p.write_text('[project]\ndependencies = ["requests>=2.28"]\n')
        doc = tomlkit.parse(p.read_text())
        result = _make_result(skipped=True)
        count = apply_updates(p, doc, [result])
        assert count == 0

    def test_error_not_applied(self, tmp_path):
        p = tmp_path / "pyproject.toml"
        p.write_text('[project]\ndependencies = ["requests>=2.28"]\n')
        doc = tomlkit.parse(p.read_text())
        result = _make_result(change_type=ChangeType.MAJOR, error="Failed")
        count = apply_updates(p, doc, [result])
        assert count == 0

    def test_multiple_sections(self, tmp_path):
        toml_str = """\
[project]
dependencies = ["requests>=2.28"]

[project.optional-dependencies]
dev = ["black>=23.0"]

[dependency-groups]
test = ["pytest>=7.0"]
"""
        p = tmp_path / "pyproject.toml"
        p.write_text(toml_str)
        doc = tomlkit.parse(p.read_text())
        results = [
            _make_result(name="requests", current_version="2.28", new_specifier=">=3.0.0"),
            _make_result(name="black", current_version="23.0", new_specifier=">=24.0"),
            _make_result(name="pytest", current_version="7.0", new_specifier=">=8.0"),
        ]
        count = apply_updates(p, doc, results)
        assert count == 3
        content = p.read_text()
        assert "requests>=3.0.0" in content
        assert "black>=24.0" in content
        assert "pytest>=8.0" in content
