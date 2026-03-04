from __future__ import annotations

from packaging.version import Version

from uv_update_check.models import ChangeType, DependencySection
from uv_update_check.resolver import (
    _format_specifier,
    classify_change,
    compute_all_updates,
    compute_update,
)


# --- classify_change ---


class TestClassifyChange:
    def test_major_bump(self):
        assert classify_change(Version("1.0.0"), Version("2.0.0")) == ChangeType.MAJOR

    def test_minor_bump(self):
        assert classify_change(Version("1.0.0"), Version("1.1.0")) == ChangeType.MINOR

    def test_patch_bump(self):
        assert classify_change(Version("1.0.0"), Version("1.0.1")) == ChangeType.PATCH

    def test_same_version(self):
        assert classify_change(Version("1.2.3"), Version("1.2.3")) == ChangeType.NONE

    def test_latest_older(self):
        assert classify_change(Version("2.0.0"), Version("1.0.0")) == ChangeType.NONE

    def test_0x_minor_is_major(self):
        """0.x minor bumps are treated as MAJOR (semver convention)."""
        assert classify_change(Version("0.1.0"), Version("0.2.0")) == ChangeType.MAJOR

    def test_0x_patch_is_major(self):
        """0.x patch bumps are also MAJOR because current.major == 0 triggers MAJOR."""
        assert classify_change(Version("0.1.0"), Version("0.1.1")) == ChangeType.MAJOR

    def test_0x_to_1x(self):
        assert classify_change(Version("0.9.0"), Version("1.0.0")) == ChangeType.MAJOR

    def test_large_version_numbers(self):
        assert classify_change(Version("10.20.30"), Version("10.20.31")) == ChangeType.PATCH


# --- compute_update ---


class TestComputeUpdate:
    def test_has_major_update(self, make_dep):
        dep = make_dep(operator=">=", current_version="1.0.0")
        result = compute_update(dep, Version("2.0.0"))
        assert result.change_type == ChangeType.MAJOR
        assert result.new_specifier == ">=2.0.0"
        assert result.latest_version == Version("2.0.0")

    def test_has_minor_update(self, make_dep):
        dep = make_dep(operator=">=", current_version="1.0.0")
        result = compute_update(dep, Version("1.2.0"))
        assert result.change_type == ChangeType.MINOR
        assert result.new_specifier == ">=1.2.0"

    def test_no_update(self, make_dep):
        dep = make_dep(operator=">=", current_version="1.0.0")
        result = compute_update(dep, Version("1.0.0"))
        assert result.change_type == ChangeType.NONE
        assert result.new_specifier == ">=1.0.0"

    def test_url_dep_skipped(self, make_dep):
        dep = make_dep(is_url=True)
        result = compute_update(dep, Version("2.0.0"))
        assert result.skipped is True
        assert result.change_type == ChangeType.NONE

    def test_unpinned_dep_skipped(self, make_dep):
        dep = make_dep(is_unpinned=True, operator="", current_version="")
        result = compute_update(dep, Version("2.0.0"))
        assert result.skipped is True
        assert result.change_type == ChangeType.NONE

    def test_latest_none_error(self, make_dep):
        dep = make_dep()
        result = compute_update(dep, None)
        assert result.error == "Failed to fetch from PyPI"
        assert result.change_type == ChangeType.NONE
        assert result.latest_version is None

    def test_caret_operator(self, make_dep):
        dep = make_dep(operator="^", current_version="1.0.0", raw_string="test-package^1.0.0")
        result = compute_update(dep, Version("1.2.0"))
        assert result.new_specifier == "^1.2.0"

    def test_tilde_equals_operator(self, make_dep):
        dep = make_dep(operator="~=", current_version="1.0.0", raw_string="test-package~=1.0.0")
        result = compute_update(dep, Version("1.3.0"))
        assert result.new_specifier == "~=1.3.0"

    def test_double_equals_operator(self, make_dep):
        dep = make_dep(operator="==", current_version="1.0.0", raw_string="test-package==1.0.0")
        result = compute_update(dep, Version("2.0.0"))
        assert result.new_specifier == "==2.0.0"

    def test_bare_version_operator(self, make_dep):
        dep = make_dep(operator="", current_version="1.0.0", raw_string="test-package 1.0.0")
        result = compute_update(dep, Version("2.0.0"))
        assert result.new_specifier == "2.0.0"


# --- compute_all_updates ---


class TestComputeAllUpdates:
    def test_multiple_deps(self, make_dep):
        deps = [
            make_dep(name="pkg-a", current_version="1.0.0"),
            make_dep(name="pkg-b", current_version="2.0.0"),
            make_dep(name="pkg-c", current_version="3.0.0"),
        ]
        versions = {
            "pkg-a": Version("2.0.0"),
            "pkg-b": Version("2.0.0"),
            "pkg-c": Version("4.0.0"),
        }
        results = compute_all_updates(deps, versions)
        assert len(results) == 3
        assert results[0].change_type == ChangeType.MAJOR
        assert results[1].change_type == ChangeType.NONE
        assert results[2].change_type == ChangeType.MAJOR

    def test_missing_from_versions_dict(self, make_dep):
        deps = [make_dep(name="missing-pkg")]
        results = compute_all_updates(deps, {})
        assert len(results) == 1
        assert results[0].error == "Failed to fetch from PyPI"

    def test_empty_list(self):
        results = compute_all_updates([], {})
        assert results == []


# --- _format_specifier ---


class TestFormatSpecifier:
    def test_caret(self):
        assert _format_specifier("^", "1.0.0") == "^1.0.0"

    def test_gte(self):
        assert _format_specifier(">=", "1.0.0") == ">=1.0.0"

    def test_all_standard_operators(self):
        for op in (">=", "<=", ">", "<", "!=", "~=", "=="):
            assert _format_specifier(op, "1.0.0") == f"{op}1.0.0"

    def test_bare(self):
        assert _format_specifier("", "1.0.0") == "1.0.0"
