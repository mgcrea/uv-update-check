from __future__ import annotations

from collections.abc import Callable

import anyio
import httpx
from packaging.version import Version

from uv_update_check.models import Dependency


async def fetch_latest_version(
    client: httpx.AsyncClient,
    package_name: str,
    include_pre: bool = False,
) -> Version | None:
    """Fetch the latest stable version of a package from PyPI."""
    url = f"https://pypi.org/pypi/{package_name}/json"
    try:
        resp = await client.get(url)
        if resp.status_code != 200:
            return None
        data = resp.json()
    except httpx.HTTPError, ValueError:
        return None

    latest_str = data.get("info", {}).get("version")
    if not latest_str:
        return None

    latest = Version(latest_str)

    # If pre-releases are excluded and the latest is a pre-release,
    # scan releases for the latest stable version
    if not include_pre and (latest.is_prerelease or latest.is_devrelease):
        releases = data.get("releases", {})
        stable = [Version(v) for v in releases if not Version(v).is_prerelease and not Version(v).is_devrelease]
        if not stable:
            return None
        return max(stable)

    return latest


async def fetch_all_versions(
    dependencies: list[Dependency],
    include_pre: bool = False,
    max_concurrent: int = 10,
    on_progress: Callable[[int, int], None] | None = None,
) -> dict[str, Version | None]:
    """Fetch latest versions for all dependencies concurrently."""
    results: dict[str, Version | None] = {}
    total = len(dependencies)
    completed = 0
    limiter = anyio.CapacityLimiter(max_concurrent)

    async def _fetch_one(dep: Dependency, client: httpx.AsyncClient) -> None:
        nonlocal completed
        async with limiter:
            version = await fetch_latest_version(client, dep.name, include_pre)
            results[dep.name] = version
            completed += 1
            if on_progress:
                on_progress(completed, total)

    async with httpx.AsyncClient(timeout=30) as client, anyio.create_task_group() as tg:
        for dep in dependencies:
            tg.start_soon(_fetch_one, dep, client)

    return results
