from __future__ import annotations

import pathlib
import re

import tomlkit
from packaging.requirements import Requirement

from uv_update_check.models import Dependency, DependencySection

# Regex to detect caret operator before packaging sees it
_CARET_RE = re.compile(
    r"^(?P<name>[A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?)(?P<extras>\[.*?\])?\s*\^(?P<version>\S+)(?P<rest>.*)$"
)


def find_pyproject(start_dir: pathlib.Path | None = None) -> pathlib.Path:
    """Find pyproject.toml by walking up from start_dir (or cwd)."""
    current = (start_dir or pathlib.Path.cwd()).resolve()
    while True:
        candidate = current / "pyproject.toml"
        if candidate.is_file():
            return candidate
        parent = current.parent
        if parent == current:
            raise FileNotFoundError("No pyproject.toml found")
        current = parent


def load_toml(path: pathlib.Path) -> tomlkit.TOMLDocument:
    """Load and return the parsed TOML document (preserving formatting)."""
    return tomlkit.parse(path.read_text())


def extract_dependencies(doc: tomlkit.TOMLDocument) -> list[Dependency]:
    """Extract all dependencies from project.dependencies, optional-dependencies, and dependency-groups."""
    deps: list[Dependency] = []

    # [project.dependencies]
    project = doc.get("project", {})
    for raw in project.get("dependencies", []):
        dep = _parse_dep_string(raw, DependencySection.MAIN)
        if dep:
            deps.append(dep)

    # [project.optional-dependencies.*]
    for group_name, group_deps in project.get("optional-dependencies", {}).items():
        for raw in group_deps:
            dep = _parse_dep_string(raw, DependencySection.OPTIONAL, group_name)
            if dep:
                deps.append(dep)

    # [dependency-groups.*]
    for group_name, group_deps in doc.get("dependency-groups", {}).items():
        for raw in group_deps:
            if not isinstance(raw, str):
                continue  # skip {include-group: "..."} entries
            dep = _parse_dep_string(raw, DependencySection.GROUP, group_name)
            if dep:
                deps.append(dep)

    return deps


def _parse_dep_string(
    raw: str,
    section: DependencySection,
    group_name: str | None = None,
) -> Dependency | None:
    """Parse a single dependency string into a Dependency object."""
    raw = raw.strip()

    # Check for caret operator (not supported by packaging)
    m = _CARET_RE.match(raw)
    if m:
        return Dependency(
            name=_normalize_name(m.group("name")),
            raw_string=raw,
            operator="^",
            current_version=m.group("version"),
            section=section,
            group_name=group_name,
            extras=_parse_extras(m.group("extras")),
        )

    # Use packaging for standard PEP 508
    try:
        req = Requirement(raw)
    except Exception:
        return None  # unparseable

    # Skip URL/git/path deps
    if req.url:
        return None

    name = _normalize_name(req.name)
    extras = req.extras
    marker = str(req.marker) if req.marker else None

    # No version specifier
    if not req.specifier:
        return Dependency(
            name=name,
            raw_string=raw,
            operator="",
            current_version="",
            section=section,
            group_name=group_name,
            extras=extras,
            marker=marker,
            is_unpinned=True,
        )

    # Take the first (primary) specifier
    specs = list(req.specifier)
    spec = specs[0]

    return Dependency(
        name=name,
        raw_string=raw,
        operator=spec.operator,
        current_version=spec.version,
        section=section,
        group_name=group_name,
        extras=extras,
        marker=marker,
    )


def _normalize_name(name: str) -> str:
    """Normalize package name (PEP 503)."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _parse_extras(extras_str: str | None) -> set[str]:
    if not extras_str:
        return set()
    return {e.strip() for e in extras_str.strip("[]").split(",")}
