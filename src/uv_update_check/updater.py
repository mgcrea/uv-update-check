from __future__ import annotations

import pathlib
import re

import tomlkit

from uv_update_check.models import ChangeType, UpdateResult


def apply_updates(
    path: pathlib.Path,
    doc: tomlkit.TOMLDocument,
    results: list[UpdateResult],
) -> int:
    """Rewrite pyproject.toml with updated version specifiers. Returns count of updates applied."""
    updatable = {
        r.dependency.name: r
        for r in results
        if r.change_type != ChangeType.NONE and not r.skipped and not r.error
    }

    if not updatable:
        return 0

    count = 0

    # Update [project.dependencies]
    project = doc.get("project", {})
    count += _update_array(project.get("dependencies", []), updatable)

    # Update [project.optional-dependencies.*]
    for _group, deps in project.get("optional-dependencies", {}).items():
        count += _update_array(deps, updatable)

    # Update [dependency-groups.*]
    for _group, deps in doc.get("dependency-groups", {}).items():
        count += _update_array(deps, updatable)

    path.write_text(tomlkit.dumps(doc))
    return count


def _update_array(
    deps_array: list,
    updatable: dict[str, UpdateResult],
) -> int:
    """Update dependency strings in a tomlkit array. Returns count of updates."""
    count = 0
    for i, raw in enumerate(deps_array):
        if not isinstance(raw, str):
            continue
        name = _extract_name(raw)
        if name in updatable:
            result = updatable[name]
            new_raw = _replace_version(raw, result)
            if new_raw != raw:
                deps_array[i] = new_raw
                count += 1
    return count


def _extract_name(raw: str) -> str:
    """Extract and normalize the package name from a dep string."""
    # Match up to the first non-name character
    m = re.match(r"([A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?)", raw.strip())
    if not m:
        return ""
    return re.sub(r"[-_.]+", "-", m.group(1)).lower()


def _replace_version(raw: str, result: UpdateResult) -> str:
    """Replace the version specifier in the raw dependency string."""
    dep = result.dependency
    old_spec = _format_old_spec(dep.operator, dep.current_version)
    new_spec = result.new_specifier

    if old_spec in raw:
        return raw.replace(old_spec, new_spec, 1)

    return raw


def _format_old_spec(operator: str, version: str) -> str:
    """Reconstruct the old specifier for string matching."""
    if operator == "^":
        return f"^{version}"
    if operator in (">=", "<=", ">", "<", "!=", "~=", "=="):
        return f"{operator}{version}"
    return version
