from __future__ import annotations

import pathlib
from typing import Annotated

import anyio
import typer
from rich.console import Console

from uv_update_check import __version__
from uv_update_check.display import display_results, make_progress
from uv_update_check.parser import extract_dependencies, find_pyproject, load_toml
from uv_update_check.pypi import fetch_all_versions
from uv_update_check.resolver import compute_all_updates
from uv_update_check.updater import apply_updates

app = typer.Typer(
    name="uuc",
    help="Check pyproject.toml dependencies for available updates.",
    no_args_is_help=False,
    add_completion=False,
)

console = Console()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"uuc {__version__}")
        raise typer.Exit()


@app.command()
def main(
    update: Annotated[bool, typer.Option("--update", "-u", help="Update pyproject.toml with new versions")] = False,
    path: Annotated[pathlib.Path | None, typer.Option("--path", "-p", help="Path to pyproject.toml")] = None,
    pre: Annotated[bool, typer.Option("--pre", help="Include pre-release versions")] = False,
    reject: Annotated[str | None, typer.Option("--reject", "-x", help="Exclude packages (comma-delimited)")] = None,
    version: Annotated[
        bool | None, typer.Option("--version", "-V", callback=_version_callback, is_eager=True, help="Show version")
    ] = None,
) -> None:
    """Check pyproject.toml dependencies for available updates."""
    anyio.run(lambda: _async_main(update, path, pre, reject))


async def _async_main(
    update: bool,
    path: pathlib.Path | None,
    pre: bool,
    reject: str | None,
) -> None:
    # 1. Find and load pyproject.toml
    try:
        if path and path.is_file():
            pyproject_path = path.resolve()
        else:
            pyproject_path = find_pyproject(path)
    except FileNotFoundError:
        console.print("[red]No pyproject.toml found[/red]")
        raise typer.Exit(1) from None

    doc = load_toml(pyproject_path)

    # 2. Extract dependencies
    deps = extract_dependencies(doc)
    # Filter out skippable deps
    fetchable = [d for d in deps if not d.is_url and not d.is_unpinned]

    if reject:
        rejected = {r.strip() for r in reject.split(",")}
        fetchable = [d for d in fetchable if d.name not in rejected]

    if not fetchable:
        console.print("No dependencies found.")
        raise typer.Exit()

    # 3. Print header
    action = "Upgrading" if update else "Checking"
    console.print(f"{action} {pyproject_path}")

    # 4. Fetch latest versions with progress bar
    progress = make_progress(len(fetchable), console)
    task_id = None

    def on_progress(completed: int, total: int) -> None:
        nonlocal task_id
        if task_id is not None:
            progress.update(task_id, completed=completed)

    with progress:
        task_id = progress.add_task("Fetching", total=len(fetchable))
        latest_versions = await fetch_all_versions(
            fetchable,
            include_pre=pre,
            on_progress=on_progress,
        )

    # 5. Compute updates
    results = compute_all_updates(fetchable, latest_versions)

    # 6. Display results
    display_results(results, str(pyproject_path), is_update=update, console=console)

    # 7. If --update, apply updates
    if update:
        apply_updates(pyproject_path, doc, results)
