from __future__ import annotations

import pytest
from packaging.version import Version

from uv_update_check.models import ChangeType, Dependency, DependencySection, UpdateResult


@pytest.fixture
def make_dep():
    """Factory fixture for creating Dependency objects with sensible defaults."""

    def _make(
        name="test-package",
        raw_string="test-package>=1.0.0",
        operator=">=",
        current_version="1.0.0",
        section=DependencySection.MAIN,
        group_name=None,
        extras=None,
        marker=None,
        is_url=False,
        is_unpinned=False,
    ):
        return Dependency(
            name=name,
            raw_string=raw_string,
            operator=operator,
            current_version=current_version,
            section=section,
            group_name=group_name,
            extras=extras or set(),
            marker=marker,
            is_url=is_url,
            is_unpinned=is_unpinned,
        )

    return _make


@pytest.fixture
def make_update_result(make_dep):
    """Factory fixture for creating UpdateResult objects."""

    def _make(
        name="test-package",
        operator=">=",
        current_version="1.0.0",
        latest_version="2.0.0",
        change_type=ChangeType.MAJOR,
        new_specifier=">=2.0.0",
        skipped=False,
        error=None,
        **dep_kwargs,
    ):
        dep = make_dep(
            name=name,
            raw_string=f"{name}{operator}{current_version}",
            operator=operator,
            current_version=current_version,
            **dep_kwargs,
        )
        return UpdateResult(
            dependency=dep,
            latest_version=Version(latest_version) if latest_version else None,
            change_type=change_type,
            new_specifier=new_specifier,
            skipped=skipped,
            error=error,
        )

    return _make
