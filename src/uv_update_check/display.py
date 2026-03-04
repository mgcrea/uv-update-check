from __future__ import annotations

from rich.console import Console
from rich.progress import MofNCompleteColumn, Progress, ProgressColumn, TaskProgressColumn
from rich.text import Text

from uv_update_check.models import ChangeType, UpdateResult

ARROW = " \u2192 "


class NcuBarColumn(ProgressColumn):
    """A progress bar that uses '=' characters like ncu."""

    def __init__(self, width: int = 20) -> None:
        super().__init__()
        self.width = width

    def render(self, task):
        completed = int(task.completed or 0)
        total = int(task.total or 1)
        filled = int(self.width * completed / total) if total else 0
        bar = "=" * filled + " " * (self.width - filled)
        return Text(f"[{bar}]")


def make_progress(total: int, console: Console) -> Progress:
    """Create a progress bar matching ncu style: [====================] 13/13 100%"""
    return Progress(
        NcuBarColumn(width=20),
        MofNCompleteColumn(),
        TaskProgressColumn(),
        console=console,
        transient=False,
    )


def display_results(
    results: list[UpdateResult],
    pyproject_path: str,
    is_update: bool = False,
    console: Console | None = None,
) -> None:
    """Print ncu-style output."""
    console = console or Console()

    # Filter to only outdated deps
    outdated = [r for r in results if r.change_type != ChangeType.NONE and not r.skipped and not r.error]

    if not outdated:
        console.print("All dependencies match the latest package versions [green bold]:)[/green bold]")
        return

    # Compute column widths for alignment
    max_name = max(len(r.dependency.name) for r in outdated)
    old_specs = [_format_specifier(r.dependency.operator, r.dependency.current_version) for r in outdated]
    max_old = max(len(s) for s in old_specs)

    console.print()

    for result, old_spec in zip(outdated, old_specs, strict=True):
        name = result.dependency.name
        new_spec = result.new_specifier
        color = _color_for_change(result.change_type)

        # Build the line: " name  old_spec  →  new_spec"
        name_padded = f" {name:<{max_name}}"
        old_padded = f"{old_spec:>{max_old}}"

        line = Text()
        line.append(name_padded)
        line.append("  ")
        line.append(old_padded)
        line.append(ARROW)
        line.append(_colorize_new_spec(old_spec, new_spec, color))

        console.print(line)

    console.print()
    if is_update:
        console.print("pyproject.toml upgraded. Run [bold]uv lock[/bold] to update the lockfile.")
    else:
        console.print("Run [bold]uuc -u[/bold] to upgrade pyproject.toml")


def _color_for_change(change_type: ChangeType) -> str:
    match change_type:
        case ChangeType.MAJOR:
            return "red"
        case ChangeType.MINOR:
            return "cyan"
        case ChangeType.PATCH:
            return "green"
        case ChangeType.NONE:
            return "dim"


def _format_specifier(operator: str, version: str) -> str:
    if operator == "^":
        return f"^{version}"
    if operator in (">=", "<=", ">", "<", "!=", "~=", "=="):
        return f"{operator}{version}"
    return version


def _colorize_new_spec(old_spec: str, new_spec: str, color: str) -> Text:
    """Colorize only the changed parts of the new version (ncu-style partial coloring)."""
    # Extract version parts from both specs
    _, old_ver = _split_spec(old_spec)
    new_op, new_ver = _split_spec(new_spec)

    text = Text()

    # Operator stays uncolored if unchanged
    if new_op:
        text.append(new_op)

    # Split version into parts and color from first difference onward
    old_parts = old_ver.split(".")
    new_parts = new_ver.split(".")

    # Find first differing index
    diff_idx = len(new_parts)
    for i, part in enumerate(new_parts):
        old_part = old_parts[i] if i < len(old_parts) else None
        if part != old_part:
            diff_idx = i
            break

    # Unchanged prefix
    if diff_idx > 0:
        text.append(".".join(new_parts[:diff_idx]))

    # Colored suffix
    if diff_idx < len(new_parts):
        if diff_idx > 0:
            text.append(".")
        text.append(".".join(new_parts[diff_idx:]), style=color)

    return text


def _split_spec(spec: str) -> tuple[str, str]:
    """Split a specifier into (operator, version)."""
    for op in (">=", "<=", "!=", "~=", "==", ">", "<", "^"):
        if spec.startswith(op):
            return op, spec[len(op) :]
    return "", spec
