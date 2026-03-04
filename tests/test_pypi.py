from __future__ import annotations

import httpx
import pytest
import respx
from packaging.version import Version

from uv_update_check.models import Dependency, DependencySection
from uv_update_check.pypi import (
    _filter_by_target,
    _stable_versions,
    fetch_all_versions,
    fetch_latest_version,
)


def _make_dep(name="requests"):
    return Dependency(
        name=name,
        raw_string=f"{name}>=1.0",
        operator=">=",
        current_version="1.0",
        section=DependencySection.MAIN,
    )


def _pypi_json(version="2.31.0", releases=None):
    """Build a mock PyPI JSON API response."""
    if releases is None:
        releases = {version: []}
    return {"info": {"version": version}, "releases": releases}


# --- _stable_versions ---


class TestStableVersions:
    def test_filters_prereleases(self):
        releases = {"1.0.0": [], "2.0.0a1": [], "2.0.0": []}
        result = _stable_versions(releases, include_pre=False)
        assert Version("1.0.0") in result
        assert Version("2.0.0") in result
        assert Version("2.0.0a1") not in result

    def test_includes_prereleases(self):
        releases = {"1.0.0": [], "2.0.0a1": []}
        result = _stable_versions(releases, include_pre=True)
        assert Version("2.0.0a1") in result

    def test_filters_dev_releases(self):
        releases = {"1.0.0": [], "1.1.0.dev1": []}
        result = _stable_versions(releases, include_pre=False)
        assert len(result) == 1
        assert result[0] == Version("1.0.0")

    def test_skips_invalid_versions(self):
        releases = {"1.0.0": [], "not-a-version": [], "2.0.0": []}
        result = _stable_versions(releases, include_pre=False)
        assert len(result) == 2

    def test_empty_releases(self):
        assert _stable_versions({}, include_pre=False) == []


# --- _filter_by_target ---


class TestFilterByTarget:
    def test_minor_same_major(self):
        versions = [Version("1.0.0"), Version("1.5.0"), Version("2.0.0")]
        result = _filter_by_target(versions, Version("1.0.0"), "minor")
        assert result == Version("1.5.0")

    def test_minor_no_match(self):
        versions = [Version("2.0.0"), Version("3.0.0")]
        result = _filter_by_target(versions, Version("1.0.0"), "minor")
        assert result is None

    def test_patch_same_major_and_minor(self):
        versions = [Version("1.0.0"), Version("1.0.5"), Version("1.1.0"), Version("2.0.0")]
        result = _filter_by_target(versions, Version("1.0.0"), "patch")
        assert result == Version("1.0.5")

    def test_patch_no_match(self):
        versions = [Version("1.1.0"), Version("2.0.0")]
        result = _filter_by_target(versions, Version("1.0.0"), "patch")
        assert result is None

    def test_latest_returns_max(self):
        """Target 'latest' is not handled by _filter_by_target (no filtering)."""
        versions = [Version("1.0.0"), Version("2.0.0"), Version("3.0.0")]
        # latest target doesn't filter, so all versions pass through
        result = _filter_by_target(versions, Version("1.0.0"), "latest")
        assert result == Version("3.0.0")


# --- fetch_latest_version ---


class TestFetchLatestVersion:
    @respx.mock
    @pytest.mark.anyio
    async def test_success(self):
        respx.get("https://pypi.org/pypi/requests/json").mock(
            return_value=httpx.Response(200, json=_pypi_json("2.31.0"))
        )
        async with httpx.AsyncClient() as client:
            result = await fetch_latest_version(client, "requests")
        assert result == Version("2.31.0")

    @respx.mock
    @pytest.mark.anyio
    async def test_404(self):
        respx.get("https://pypi.org/pypi/nonexistent/json").mock(return_value=httpx.Response(404))
        async with httpx.AsyncClient() as client:
            result = await fetch_latest_version(client, "nonexistent")
        assert result is None

    @respx.mock
    @pytest.mark.anyio
    async def test_network_error(self):
        respx.get("https://pypi.org/pypi/requests/json").mock(side_effect=httpx.ConnectError("fail"))
        async with httpx.AsyncClient() as client:
            result = await fetch_latest_version(client, "requests")
        assert result is None

    @respx.mock
    @pytest.mark.anyio
    async def test_missing_info_version(self):
        respx.get("https://pypi.org/pypi/requests/json").mock(return_value=httpx.Response(200, json={"info": {}}))
        async with httpx.AsyncClient() as client:
            result = await fetch_latest_version(client, "requests")
        assert result is None

    @respx.mock
    @pytest.mark.anyio
    async def test_prerelease_excluded(self):
        releases = {"2.31.0": [], "3.0.0a1": []}
        respx.get("https://pypi.org/pypi/requests/json").mock(
            return_value=httpx.Response(200, json=_pypi_json("3.0.0a1", releases))
        )
        async with httpx.AsyncClient() as client:
            result = await fetch_latest_version(client, "requests", include_pre=False)
        assert result == Version("2.31.0")

    @respx.mock
    @pytest.mark.anyio
    async def test_prerelease_included(self):
        respx.get("https://pypi.org/pypi/requests/json").mock(
            return_value=httpx.Response(200, json=_pypi_json("3.0.0a1"))
        )
        async with httpx.AsyncClient() as client:
            result = await fetch_latest_version(client, "requests", include_pre=True)
        assert result == Version("3.0.0a1")

    @respx.mock
    @pytest.mark.anyio
    async def test_all_prereleases_returns_none(self):
        releases = {"1.0.0a1": [], "2.0.0b1": []}
        respx.get("https://pypi.org/pypi/requests/json").mock(
            return_value=httpx.Response(200, json=_pypi_json("2.0.0b1", releases))
        )
        async with httpx.AsyncClient() as client:
            result = await fetch_latest_version(client, "requests", include_pre=False)
        assert result is None

    @respx.mock
    @pytest.mark.anyio
    async def test_dev_release_excluded(self):
        releases = {"1.0.0": [], "2.0.0.dev1": []}
        respx.get("https://pypi.org/pypi/requests/json").mock(
            return_value=httpx.Response(200, json=_pypi_json("2.0.0.dev1", releases))
        )
        async with httpx.AsyncClient() as client:
            result = await fetch_latest_version(client, "requests", include_pre=False)
        assert result == Version("1.0.0")

    @respx.mock
    @pytest.mark.anyio
    async def test_picks_highest_stable(self):
        releases = {"1.0.0": [], "2.0.0": [], "1.5.0": [], "3.0.0a1": []}
        respx.get("https://pypi.org/pypi/requests/json").mock(
            return_value=httpx.Response(200, json=_pypi_json("3.0.0a1", releases))
        )
        async with httpx.AsyncClient() as client:
            result = await fetch_latest_version(client, "requests", include_pre=False)
        assert result == Version("2.0.0")

    @respx.mock
    @pytest.mark.anyio
    async def test_target_minor(self):
        releases = {"1.0.0": [], "1.5.0": [], "2.0.0": []}
        respx.get("https://pypi.org/pypi/requests/json").mock(
            return_value=httpx.Response(200, json=_pypi_json("2.0.0", releases))
        )
        async with httpx.AsyncClient() as client:
            result = await fetch_latest_version(client, "requests", current_version="1.0.0", target="minor")
        assert result == Version("1.5.0")

    @respx.mock
    @pytest.mark.anyio
    async def test_target_patch(self):
        releases = {"1.0.0": [], "1.0.3": [], "1.1.0": [], "2.0.0": []}
        respx.get("https://pypi.org/pypi/requests/json").mock(
            return_value=httpx.Response(200, json=_pypi_json("2.0.0", releases))
        )
        async with httpx.AsyncClient() as client:
            result = await fetch_latest_version(client, "requests", current_version="1.0.0", target="patch")
        assert result == Version("1.0.3")

    @respx.mock
    @pytest.mark.anyio
    async def test_target_minor_no_match(self):
        releases = {"2.0.0": [], "3.0.0": []}
        respx.get("https://pypi.org/pypi/requests/json").mock(
            return_value=httpx.Response(200, json=_pypi_json("3.0.0", releases))
        )
        async with httpx.AsyncClient() as client:
            result = await fetch_latest_version(client, "requests", current_version="1.0.0", target="minor")
        assert result is None

    @respx.mock
    @pytest.mark.anyio
    async def test_target_latest_ignores_current(self):
        releases = {"1.0.0": [], "2.0.0": [], "3.0.0": []}
        respx.get("https://pypi.org/pypi/requests/json").mock(
            return_value=httpx.Response(200, json=_pypi_json("3.0.0", releases))
        )
        async with httpx.AsyncClient() as client:
            result = await fetch_latest_version(client, "requests", current_version="1.0.0", target="latest")
        assert result == Version("3.0.0")


# --- fetch_all_versions ---


class TestFetchAllVersions:
    @respx.mock
    @pytest.mark.anyio
    async def test_multiple_deps(self):
        respx.get("https://pypi.org/pypi/requests/json").mock(
            return_value=httpx.Response(200, json=_pypi_json("2.31.0"))
        )
        respx.get("https://pypi.org/pypi/click/json").mock(return_value=httpx.Response(200, json=_pypi_json("8.1.0")))
        deps = [_make_dep("requests"), _make_dep("click")]
        results = await fetch_all_versions(deps)
        assert results["requests"] == Version("2.31.0")
        assert results["click"] == Version("8.1.0")

    @respx.mock
    @pytest.mark.anyio
    async def test_progress_callback(self):
        respx.get("https://pypi.org/pypi/requests/json").mock(
            return_value=httpx.Response(200, json=_pypi_json("2.31.0"))
        )
        respx.get("https://pypi.org/pypi/click/json").mock(return_value=httpx.Response(200, json=_pypi_json("8.1.0")))
        calls = []
        deps = [_make_dep("requests"), _make_dep("click")]
        await fetch_all_versions(deps, on_progress=lambda c, t: calls.append((c, t)))
        assert len(calls) == 2
        # Both should report total=2
        assert all(t == 2 for _, t in calls)

    @respx.mock
    @pytest.mark.anyio
    async def test_partial_failure(self):
        respx.get("https://pypi.org/pypi/requests/json").mock(
            return_value=httpx.Response(200, json=_pypi_json("2.31.0"))
        )
        respx.get("https://pypi.org/pypi/missing/json").mock(return_value=httpx.Response(404))
        deps = [_make_dep("requests"), _make_dep("missing")]
        results = await fetch_all_versions(deps)
        assert results["requests"] == Version("2.31.0")
        assert results["missing"] is None

    @respx.mock
    @pytest.mark.anyio
    async def test_target_passed_through(self):
        """Target param is forwarded to fetch_latest_version."""
        releases = {"1.0.0": [], "1.5.0": [], "2.0.0": []}
        respx.get("https://pypi.org/pypi/requests/json").mock(
            return_value=httpx.Response(200, json=_pypi_json("2.0.0", releases))
        )
        deps = [_make_dep("requests")]
        results = await fetch_all_versions(deps, target="minor")
        # dep.current_version is "1.0", so minor target keeps major=1 -> 1.5.0
        assert results["requests"] == Version("1.5.0")

    @respx.mock
    @pytest.mark.anyio
    async def test_empty_deps(self):
        results = await fetch_all_versions([])
        assert results == {}
