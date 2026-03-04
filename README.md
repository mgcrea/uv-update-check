# uuc — uv update check

<p>
  <a href="https://pypi.org/project/uv-update-check">
    <img src="https://img.shields.io/pypi/v/uv-update-check.svg?style=for-the-badge" alt="pypi version" />
  </a>
  <a href="https://pypi.org/project/uv-update-check">
    <img src="https://img.shields.io/pypi/dm/uv-update-check.svg?style=for-the-badge" alt="pypi monthly downloads" />
  </a>
  <a href="https://pypi.org/project/uv-update-check">
    <img src="https://img.shields.io/pypi/l/uv-update-check.svg?style=for-the-badge" alt="pypi license" />
  </a>
  <a href="https://github.com/mgcrea/uv-update-check/actions/workflows/ci.yml">
    <img src="https://img.shields.io/github/actions/workflow/status/mgcrea/uv-update-check/ci.yml?style=for-the-badge&branch=main" alt="build status" />
  </a>
  <a href="https://pypi.org/project/uv-update-check">
    <img src="https://img.shields.io/pypi/pyversions/uv-update-check.svg?style=for-the-badge" alt="python versions" />
  </a>
  <a href="https://github.com/mgcrea/uv-update-check/actions/workflows/ci.yml">
    <img src="https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/mgcrea/432a6756ff172befcbb5fefc47374a2e/raw/coverage.json&style=for-the-badge" alt="coverage" />
  </a>
</p>

A minimalist [npm-check-updates](https://github.com/raineorshine/npm-check-updates) equivalent for [uv](https://docs.astral.sh/uv/) projects. Check your `pyproject.toml` dependencies against PyPI and see what's outdated — in the exact same output style as `ncu`.

```
$ uuc
Checking /path/to/pyproject.toml
[====================] 9/9 100%

 httpx           >=0.27 → >=0.28.1
 rich              >=13 → >=14.3.3
 typer           >=0.12 → >=0.24.1
 pytest             >=8 → >=9.0.2
 pytest-asyncio  >=0.24 → >=1.3.0

Run uuc -u to upgrade pyproject.toml
```

Updates are **color-coded** by severity: <span style="color:red">red</span> for major, <span style="color:cyan">cyan</span> for minor, <span style="color:green">green</span> for patch — with partial version coloring just like `ncu`.

## Install

```bash
uv tool install uv-update-check
```

Or run directly without installing:

```bash
uvx uv-update-check
```

## Usage

```bash
# Show outdated dependencies (read-only, default)
uuc

# Update pyproject.toml with latest versions
uuc -u

# Only show minor/patch updates (no breaking changes)
uuc -t minor

# Only show patch updates
uuc -t patch

# Exclude specific packages
uuc -x httpx,rich

# Check a specific project
uuc --path /path/to/pyproject.toml

# Include pre-release versions
uuc --pre

# Combine flags
uuc -t minor -x httpx -u
```

### Options

| Flag | Description |
|---|---|
| `-u`, `--update` | Rewrite `pyproject.toml` with new versions |
| `-t`, `--target` | Target version level: `latest` (default), `minor`, `patch` |
| `-x`, `--reject` | Exclude packages (comma-delimited) |
| `-p`, `--path` | Path to `pyproject.toml` (default: search from cwd) |
| `--pre` | Include pre-release versions |
| `-V`, `--version` | Show version |

## What it checks

`uuc` discovers dependencies from all standard `pyproject.toml` sections:

- `[project.dependencies]`
- `[project.optional-dependencies.*]`
- `[dependency-groups.*]` (PEP 735)

It supports all common version specifiers: `>=`, `~=`, `==`, `^`, `>`, `<`, `!=`.

### What it skips

- URL, git, and path dependencies
- Dependencies with no version specifier
- `{include-group = "..."}` entries in dependency groups

## How it works

1. Finds and parses `pyproject.toml` using [tomlkit](https://github.com/sdispater/tomlkit) (preserves formatting and comments)
2. Extracts all dependencies from the sections above
3. Fetches latest versions from the [PyPI JSON API](https://pypi.org/pypi/{package}/json) concurrently using [httpx](https://www.python-httpx.org/) + [anyio](https://anyio.readthedocs.io/)
4. Compares versions using [packaging](https://packaging.pypa.io/) with semver-aware classification
5. Displays results in ncu-style output with [Rich](https://rich.readthedocs.io/)
6. With `-u`, rewrites `pyproject.toml` in-place preserving all formatting, comments, and ordering

## Differences from similar tools

| Tool | What it does | How `uuc` differs |
|---|---|---|
| `uv lock --upgrade` | Upgrades within existing constraints | `uuc` shows what's available *beyond* your constraints |
| `uv pip list --outdated` | Shows outdated installed packages | `uuc` checks `pyproject.toml` constraints, not installed versions |
| `pip-check-updates` | Similar concept | `uuc` is uv-native with dependency-groups support |

## Requirements

- Python >= 3.14

## License

MIT
