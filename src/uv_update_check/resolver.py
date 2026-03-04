from __future__ import annotations

from packaging.version import Version

from uv_update_check.models import ChangeType, Dependency, UpdateResult


def classify_change(current: Version, latest: Version) -> ChangeType:
    """Classify the version change type between current and latest."""
    if latest <= current:
        return ChangeType.NONE

    # For 0.x, any minor bump is major (semver convention)
    if current.major == 0 or latest.major != current.major:
        return ChangeType.MAJOR
    if latest.minor != current.minor:
        return ChangeType.MINOR
    return ChangeType.PATCH


def compute_update(dep: Dependency, latest: Version | None) -> UpdateResult:
    """Determine the update result for a single dependency."""
    if dep.is_url or dep.is_unpinned:
        return UpdateResult(
            dependency=dep,
            latest_version=latest,
            change_type=ChangeType.NONE,
            new_specifier="",
            skipped=True,
        )

    if latest is None:
        return UpdateResult(
            dependency=dep,
            latest_version=None,
            change_type=ChangeType.NONE,
            new_specifier="",
            error="Failed to fetch from PyPI",
        )

    current = Version(dep.current_version)
    change_type = classify_change(current, latest)

    if change_type == ChangeType.NONE:
        return UpdateResult(
            dependency=dep,
            latest_version=latest,
            change_type=ChangeType.NONE,
            new_specifier=_format_specifier(dep.operator, dep.current_version),
        )

    new_specifier = _format_specifier(dep.operator, str(latest))
    return UpdateResult(
        dependency=dep,
        latest_version=latest,
        change_type=change_type,
        new_specifier=new_specifier,
    )


def compute_all_updates(
    dependencies: list[Dependency],
    latest_versions: dict[str, Version | None],
) -> list[UpdateResult]:
    """Compute updates for all dependencies."""
    return [compute_update(dep, latest_versions.get(dep.name)) for dep in dependencies]


def _format_specifier(operator: str, version: str) -> str:
    """Reconstruct a specifier string preserving the original operator style."""
    if operator == "^":
        return f"^{version}"
    if operator in (">=", "<=", ">", "<", "!=", "~=", "=="):
        return f"{operator}{version}"
    return version
