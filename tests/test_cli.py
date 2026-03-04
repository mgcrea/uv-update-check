from __future__ import annotations

import httpx
import pytest
import respx
from typer.testing import CliRunner

from uv_update_check.cli import app

runner = CliRunner()


def _pypi_json(version="2.0.0", releases=None):
    if releases is None:
        releases = {version: []}
    return {"info": {"version": version}, "releases": releases}


# --- --reject / -x flag ---


class TestRejectFlag:
    @respx.mock
    def test_reject_excludes_package(self, tmp_path):
        toml = '[project]\ndependencies = ["requests>=2.28", "click>=8.0"]\n'
        p = tmp_path / "pyproject.toml"
        p.write_text(toml)

        releases = {"2.28": [], "3.0.0": []}
        respx.get("https://pypi.org/pypi/click/json").mock(
            return_value=httpx.Response(200, json=_pypi_json("3.0.0", releases))
        )
        # requests should NOT be fetched since it's rejected
        result = runner.invoke(app, ["--path", str(p), "--reject", "requests"])
        assert result.exit_code == 0
        assert "click" in result.output
        # requests was excluded, so no PyPI call for it
        assert respx.calls.call_count == 1

    @respx.mock
    def test_reject_multiple_packages(self, tmp_path):
        toml = '[project]\ndependencies = ["requests>=2.28", "click>=8.0", "rich>=13"]\n'
        p = tmp_path / "pyproject.toml"
        p.write_text(toml)

        releases = {"13": [], "14.0.0": []}
        respx.get("https://pypi.org/pypi/rich/json").mock(
            return_value=httpx.Response(200, json=_pypi_json("14.0.0", releases))
        )
        result = runner.invoke(app, ["--path", str(p), "--reject", "requests, click"])
        assert result.exit_code == 0
        # Only rich should be checked
        assert respx.calls.call_count == 1

    @respx.mock
    def test_reject_all_exits_early(self, tmp_path):
        toml = '[project]\ndependencies = ["requests>=2.28"]\n'
        p = tmp_path / "pyproject.toml"
        p.write_text(toml)

        result = runner.invoke(app, ["--path", str(p), "--reject", "requests"])
        assert result.exit_code == 0
        assert "No dependencies found" in result.output


# --- --target / -t flag ---


class TestTargetFlag:
    def test_invalid_target_exits_with_error(self, tmp_path):
        p = tmp_path / "pyproject.toml"
        p.write_text('[project]\ndependencies = ["requests>=2.28"]\n')

        result = runner.invoke(app, ["--path", str(p), "--target", "invalid"])
        assert result.exit_code == 1
        assert "Invalid target" in result.output

    @respx.mock
    def test_target_minor(self, tmp_path):
        toml = '[project]\ndependencies = ["requests>=1.0.0"]\n'
        p = tmp_path / "pyproject.toml"
        p.write_text(toml)

        releases = {"1.0.0": [], "1.5.0": [], "2.0.0": []}
        respx.get("https://pypi.org/pypi/requests/json").mock(
            return_value=httpx.Response(200, json=_pypi_json("2.0.0", releases))
        )
        result = runner.invoke(app, ["--path", str(p), "--target", "minor"])
        assert result.exit_code == 0
        # Should show 1.5.0 (same major), not 2.0.0
        assert "1.5.0" in result.output

    @respx.mock
    def test_target_patch(self, tmp_path):
        toml = '[project]\ndependencies = ["requests>=1.0.0"]\n'
        p = tmp_path / "pyproject.toml"
        p.write_text(toml)

        releases = {"1.0.0": [], "1.0.5": [], "1.1.0": [], "2.0.0": []}
        respx.get("https://pypi.org/pypi/requests/json").mock(
            return_value=httpx.Response(200, json=_pypi_json("2.0.0", releases))
        )
        result = runner.invoke(app, ["--path", str(p), "--target", "patch"])
        assert result.exit_code == 0
        assert "1.0.5" in result.output

    @respx.mock
    def test_target_latest_default(self, tmp_path):
        toml = '[project]\ndependencies = ["requests>=1.0.0"]\n'
        p = tmp_path / "pyproject.toml"
        p.write_text(toml)

        releases = {"1.0.0": [], "2.0.0": []}
        respx.get("https://pypi.org/pypi/requests/json").mock(
            return_value=httpx.Response(200, json=_pypi_json("2.0.0", releases))
        )
        result = runner.invoke(app, ["--path", str(p)])
        assert result.exit_code == 0
        assert "2.0.0" in result.output
