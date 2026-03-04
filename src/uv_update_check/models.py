from dataclasses import dataclass, field
from enum import Enum

from packaging.version import Version


class ChangeType(Enum):
    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"
    NONE = "none"


class DependencySection(Enum):
    MAIN = "dependencies"
    OPTIONAL = "optional-dependencies"
    GROUP = "dependency-groups"


@dataclass
class Dependency:
    name: str
    raw_string: str
    operator: str
    current_version: str
    section: DependencySection
    group_name: str | None = None
    extras: set[str] = field(default_factory=set)
    marker: str | None = None
    is_url: bool = False
    is_unpinned: bool = False


@dataclass
class UpdateResult:
    dependency: Dependency
    latest_version: Version | None
    change_type: ChangeType
    new_specifier: str
    skipped: bool = False
    error: str | None = None
