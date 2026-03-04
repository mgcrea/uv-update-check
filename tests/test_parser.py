from __future__ import annotations

import pytest
import tomlkit

from uv_update_check.models import DependencySection
from uv_update_check.parser import (
    _normalize_name,
    _parse_dep_string,
    _parse_extras,
    extract_dependencies,
    find_pyproject,
    load_toml,
)

# --- find_pyproject ---


class TestFindPyproject:
    def test_in_current_dir(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        result = find_pyproject(tmp_path)
        assert result == tmp_path / "pyproject.toml"

    def test_in_parent_dir(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        sub = tmp_path / "sub"
        sub.mkdir()
        result = find_pyproject(sub)
        assert result == tmp_path / "pyproject.toml"

    def test_not_found(self, tmp_path):
        # Use a deep tmp dir unlikely to have pyproject.toml above it
        deep = tmp_path / "a" / "b" / "c"
        deep.mkdir(parents=True)
        # Mock by checking that we eventually reach root without finding it
        with pytest.raises(FileNotFoundError, match="No pyproject.toml found"):
            find_pyproject(deep)


# --- load_toml ---


class TestLoadToml:
    def test_valid(self, tmp_path):
        p = tmp_path / "pyproject.toml"
        p.write_text('[project]\nname = "test"\n')
        doc = load_toml(p)
        assert doc["project"]["name"] == "test"


# --- _normalize_name ---


class TestNormalizeName:
    def test_underscores(self):
        assert _normalize_name("my_package") == "my-package"

    def test_dots(self):
        assert _normalize_name("my.package") == "my-package"

    def test_mixed_separators(self):
        assert _normalize_name("My_.Package") == "my-package"

    def test_uppercase(self):
        assert _normalize_name("MyPackage") == "mypackage"

    def test_consecutive_separators(self):
        assert _normalize_name("my___package") == "my-package"

    def test_already_normalized(self):
        assert _normalize_name("my-package") == "my-package"


# --- _parse_extras ---


class TestParseExtras:
    def test_none(self):
        assert _parse_extras(None) == set()

    def test_empty_string(self):
        assert _parse_extras("") == set()

    def test_single(self):
        assert _parse_extras("[dev]") == {"dev"}

    def test_multiple(self):
        assert _parse_extras("[dev, test]") == {"dev", "test"}


# --- _parse_dep_string ---


class TestParseDepString:
    def test_gte(self):
        dep = _parse_dep_string("requests>=2.28", DependencySection.MAIN)
        assert dep is not None
        assert dep.name == "requests"
        assert dep.operator == ">="
        assert dep.current_version == "2.28"

    def test_eq(self):
        dep = _parse_dep_string("requests==2.28.0", DependencySection.MAIN)
        assert dep is not None
        assert dep.operator == "=="
        assert dep.current_version == "2.28.0"

    def test_caret(self):
        dep = _parse_dep_string("requests^2.28", DependencySection.MAIN)
        assert dep is not None
        assert dep.operator == "^"
        assert dep.current_version == "2.28"

    def test_caret_with_extras(self):
        dep = _parse_dep_string("httpx[http2]^0.27", DependencySection.MAIN)
        assert dep is not None
        assert dep.operator == "^"
        assert dep.current_version == "0.27"
        assert "http2" in dep.extras

    def test_with_extras(self):
        dep = _parse_dep_string("package[extra1,extra2]>=1.0", DependencySection.MAIN)
        assert dep is not None
        assert "extra1" in dep.extras
        assert "extra2" in dep.extras

    def test_with_marker(self):
        dep = _parse_dep_string("requests>=2.28 ; python_version>='3.8'", DependencySection.MAIN)
        assert dep is not None
        assert dep.marker is not None
        assert "python_version" in dep.marker

    def test_unpinned(self):
        dep = _parse_dep_string("requests", DependencySection.MAIN)
        assert dep is not None
        assert dep.is_unpinned is True
        assert dep.operator == ""
        assert dep.current_version == ""

    def test_url_dep_returns_none(self):
        dep = _parse_dep_string("package @ https://example.com/pkg.tar.gz", DependencySection.MAIN)
        assert dep is None

    def test_tilde_equals(self):
        dep = _parse_dep_string("requests~=2.28", DependencySection.MAIN)
        assert dep is not None
        assert dep.operator == "~="
        assert dep.current_version == "2.28"

    def test_name_normalization(self):
        dep = _parse_dep_string("My_Package>=1.0", DependencySection.MAIN)
        assert dep is not None
        assert dep.name == "my-package"

    def test_section_and_group(self):
        dep = _parse_dep_string("pytest>=8", DependencySection.GROUP, group_name="dev")
        assert dep is not None
        assert dep.section == DependencySection.GROUP
        assert dep.group_name == "dev"

    def test_caret_ignores_marker(self):
        """Caret branch doesn't parse markers from the rest group."""
        dep = _parse_dep_string("package^1.0 ; python_version>='3.8'", DependencySection.MAIN)
        assert dep is not None
        assert dep.operator == "^"
        assert dep.marker is None


# --- extract_dependencies ---


class TestExtractDependencies:
    def test_main_section(self):
        doc = tomlkit.parse('[project]\ndependencies = ["requests>=2.28"]\n')
        deps = extract_dependencies(doc)
        assert len(deps) == 1
        assert deps[0].section == DependencySection.MAIN
        assert deps[0].name == "requests"

    def test_optional_section(self):
        doc = tomlkit.parse('[project.optional-dependencies]\ndev = ["pytest>=8"]\n')
        deps = extract_dependencies(doc)
        assert len(deps) == 1
        assert deps[0].section == DependencySection.OPTIONAL
        assert deps[0].group_name == "dev"

    def test_group_section(self):
        doc = tomlkit.parse('[dependency-groups]\ntest = ["pytest>=8"]\n')
        deps = extract_dependencies(doc)
        assert len(deps) == 1
        assert deps[0].section == DependencySection.GROUP
        assert deps[0].group_name == "test"

    def test_all_sections(self):
        toml_str = """\
[project]
dependencies = ["requests>=2.28"]

[project.optional-dependencies]
dev = ["black>=23"]

[dependency-groups]
test = ["pytest>=8"]
"""
        doc = tomlkit.parse(toml_str)
        deps = extract_dependencies(doc)
        assert len(deps) == 3
        sections = {d.section for d in deps}
        assert sections == {DependencySection.MAIN, DependencySection.OPTIONAL, DependencySection.GROUP}

    def test_include_group_skipped(self):
        toml_str = """\
[dependency-groups]
test = [{include-group = "dev"}, "pytest>=8"]
"""
        doc = tomlkit.parse(toml_str)
        deps = extract_dependencies(doc)
        assert len(deps) == 1
        assert deps[0].name == "pytest"

    def test_empty_toml(self):
        doc = tomlkit.parse("")
        deps = extract_dependencies(doc)
        assert deps == []

    def test_url_deps_excluded(self):
        doc = tomlkit.parse('[project]\ndependencies = ["pkg @ https://example.com/pkg.tar.gz"]\n')
        deps = extract_dependencies(doc)
        assert deps == []
