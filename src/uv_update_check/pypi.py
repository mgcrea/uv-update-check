from __future__ import annotations

from collections.abc import Callable

import anyio
import httpx
from packaging.version import Version

from uv_update_check.models import Dependency


def _stable_versions(releases: dict, include_pre: bool) -> list[Version]:
    """Parse release keys into a sorted list of stable versions."""
    versions = []
    for v in releases:
        try:
            ver = Version(v)
        except Exception:
            continue
        if not include_pre and (ver.is_prerelease or ver.is_devrelease):
            continue
        versions.append(ver)
    return versions


def _filter_by_target(versions: list[Version], current: Version, target: str) -> Version | None:
    """Find the greatest version matching the target constraint."""
    if target == "minor":
        versions = [v for v in versions if v.major == current.major]
    elif target == "patch":
        versions = [v for v in versions if v.major == current.major and v.minor == current.minor]
    return max(versions) if versions else None


async def fetch_latest_version(
    client: httpx.AsyncClient,
    package_name: str,
    current_version: str | None = None,
    target: str = "latest",
    include_pre: bool = False,
) -> Version | None:
    """Fetch the target version of a package from PyPI."""
    url = f"https://pypi.org/pypi/{package_name}/json"
    try:
        resp = await client.get(url)
        if resp.status_code != 200:
            return None
        data = resp.json()
    except httpx.HTTPError, ValueError:
        return None

    releases = data.get("releases", {})
    stable = _stable_versions(releases, include_pre)

    if not stable:
        return None

    # For minor/patch targets, filter by current version constraint
    if target in ("minor", "patch") and current_version:
        current = Version(current_version)
        return _filter_by_target(stable, current, target)

    # For "latest", just return the highest stable version
    return max(stable)


async def fetch_all_versions(
    dependencies: list[Dependency],
    target: str = "latest",
    include_pre: bool = False,
    max_concurrent: int = 10,
    on_progress: Callable[[int, int], None] | None = None,
) -> dict[str, Version | None]:
    """Fetch target versions for all dependencies concurrently."""
    results: dict[str, Version | None] = {}
    total = len(dependencies)
    completed = 0
    limiter = anyio.CapacityLimiter(max_concurrent)

    async def _fetch_one(dep: Dependency, client: httpx.AsyncClient) -> None:
        nonlocal completed
        async with limiter:
            version = await fetch_latest_version(client, dep.name, dep.current_version, target, include_pre)
            results[dep.name] = version
            completed += 1
            if on_progress:
                on_progress(completed, total)

    async with httpx.AsyncClient(timeout=30) as client, anyio.create_task_group() as tg:
        for dep in dependencies:
            tg.start_soon(_fetch_one, dep, client)

    return results
