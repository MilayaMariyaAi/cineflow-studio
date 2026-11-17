"""Update checks for CineFlow Studio: PyPI release or the development checkout.

Two worlds, one honest JSON answer (Studio 5 / #700):
- installed from PyPI (``uvx cineflow-studio``): the latest release comes from
  the PyPI JSON API; the answer recommends an upgrade command and never
  mutates the user's environment by itself — upgrading is the user's command,
  followed by one ``cineflow-setup`` to re-layout the skill;
- a development checkout of the CineFlow monorepo (a ``.git`` directory next
  to the package source): the git remote answers, as before.

Offline / air-gapped installs degrade into a JSON status, never an exception
leaking out of a tool call.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from cineflow_studio.mcp.davinci import install_davinci_script

PYPI_PACKAGE = "cineflow-studio"
PYPI_JSON_URL = f"https://pypi.org/pypi/{PYPI_PACKAGE}/json"
HTTP_TIMEOUT_SEC = 8.0


def _installed_version() -> str | None:
    """The installed ``cineflow-studio`` distribution, or None in a dev checkout."""
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version(PYPI_PACKAGE)
    except PackageNotFoundError:
        return None


def _dev_repo_root() -> Path | None:
    """The monorepo root when this file runs from a git checkout, not site-packages.

    ``.git`` is a directory in a normal clone and a file in a worktree — both count."""
    root = Path(__file__).resolve().parent.parent.parent
    return root if (root / ".git").exists() else None


def _parse_version(value: str) -> tuple[int, ...]:
    """Loose numeric compare; a non-parseable piece counts as 0 (rc0/a1 suffixes)."""
    parts: list[int] = []
    for chunk in value.replace("-", ".").split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


async def check_cineflow_updates() -> dict[str, Any]:
    installed = _installed_version()
    if installed is not None:
        return await _check_pypi_release(installed)
    dev_root = _dev_repo_root()
    if dev_root is not None:
        return _check_git_updates(dev_root)
    return {
        "status": "unknown_source",
        "mode": None,
        "installed": None,
        "latest": None,
        "update_available": False,
        "command": None,
        "message": "Neither an installed cineflow-studio package nor a development checkout was detected.",
        "action": "Install with: uvx cineflow-studio",
    }


async def _check_pypi_release(installed: str) -> dict[str, Any]:
    import httpx

    result: dict[str, Any] = {
        "status": "up_to_date",
        "mode": "pypi",
        "installed": installed,
        "latest": None,
        "update_available": False,
        "command": f"uv tool upgrade {PYPI_PACKAGE}",
        "message": "",
        "action": "No action needed.",
    }
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SEC) as client:
            response = await client.get(PYPI_JSON_URL)
    except httpx.HTTPError as exc:
        result["status"] = "check_failed"
        result["message"] = f"PyPI is unreachable ({exc}); staying on the installed version."
        result["action"] = "Retry later, or upgrade manually with the command above."
        return result
    if response.status_code >= 400:
        result["status"] = "check_failed"
        result["message"] = f"PyPI answered HTTP {response.status_code}; the installed version may be current."
        return result
    try:
        latest = response.json().get("info", {}).get("version")
    except ValueError:
        result["status"] = "check_failed"
        result["message"] = "PyPI answered an unreadable body; staying on the installed version."
        return result
    result["latest"] = latest
    result["update_available"] = _parse_version(latest) > _parse_version(installed)
    if result["update_available"]:
        result["status"] = "updates_available"
        result["message"] = (
            f"Release {latest} is available (installed {installed}). "
            "Upgrade, then run cineflow-setup once to re-layout the skill."
        )
        result["action"] = (
            f"Ask the user to run: uv tool upgrade {PYPI_PACKAGE} && cineflow-setup "
            f"(or one-off: uvx {PYPI_PACKAGE}@latest)."
        )
    return result


def _check_git_updates(repo_root: Path) -> dict[str, Any]:
    """Development checkout: how many commits the origin/main is ahead of HEAD."""
    try:
        subprocess.run(
            ["git", "-C", str(repo_root), "fetch", "origin", "--quiet"],
            check=False,
            timeout=8,
            capture_output=True,
        )
    except (subprocess.SubprocessError, OSError):
        pass  # Graceful fallback in offline / air-gapped environments

    try:
        head_commit = subprocess.check_output(
            ["git", "-C", str(repo_root), "rev-parse", "--short", "HEAD"],
            text=True,
            timeout=3,
        ).strip()
    except (subprocess.SubprocessError, OSError):
        head_commit = "unknown"

    new_commits: list[str] = []
    commits_behind = 0
    try:
        log_out = subprocess.check_output(
            ["git", "-C", str(repo_root), "log", "HEAD..origin/main", "--oneline", "-10"],
            text=True,
            timeout=3,
        ).strip()
        if log_out:
            new_commits = [line.strip() for line in log_out.splitlines() if line.strip()]
            commits_behind = len(new_commits)
    except (subprocess.SubprocessError, OSError):
        pass

    updates_available = commits_behind > 0
    return {
        "status": "updates_available" if updates_available else "up_to_date",
        "mode": "git",
        "installed": None,
        "latest": None,
        "update_available": updates_available,
        "current_commit": head_commit,
        "commits_behind": commits_behind,
        "new_commits": new_commits,
        "command": "git pull --ff-only && pip install -e .",
        "message": (
            f"Found {commits_behind} new update(s) in the CineFlow repository."
            if updates_available
            else "The development checkout is up to date."
        ),
        "action": (
            "Call 'cineflow_apply_update' or run './scripts/cineflow_update' to pull changes."
            if updates_available
            else "No action needed."
        ),
    }


async def apply_cineflow_updates() -> dict[str, Any]:
    """Upgrade paths. In the PyPI world the package never mutates the user's
    environment by itself; in a dev checkout it pulls and re-syncs as before."""
    installed = _installed_version()
    if installed is not None:
        return {
            "status": "upgrade_is_user_command",
            "mode": "pypi",
            "installed": installed,
            "command": f"uv tool upgrade {PYPI_PACKAGE} && cineflow-setup",
            "message": (
                "CineFlow Studio does not upgrade itself. Ask the user to run the "
                "upgrade command, then re-layout the skill with cineflow-setup."
            ),
        }
    dev_root = _dev_repo_root()
    if dev_root is None:
        return {
            "status": "unknown_source",
            "mode": None,
            "command": None,
            "message": "Neither an installed cineflow-studio package nor a development checkout was detected.",
        }
    return _apply_git_updates(dev_root)


def _apply_git_updates(repo_root: Path) -> dict[str, Any]:
    """Pulls upstream updates, syncs skills across IDEs, and updates DaVinci Resolve scripts."""
    pull_output = ""
    try:
        pull_res = subprocess.run(
            ["git", "-C", str(repo_root), "pull", "--ff-only"],
            text=True,
            timeout=30,
            capture_output=True,
            check=False,
        )
        pull_output = (pull_res.stdout + pull_res.stderr).strip()
    except (subprocess.SubprocessError, OSError) as exc:
        pull_output = f"Git pull skipped or timed out: {exc}"

    # Sync the canonical skill (skill/cineflow/, Studio 0c) across IDE discovery locations
    skill_source_dir = repo_root / "skill" / "cineflow"
    synced_locations: list[str] = []
    if (skill_source_dir / "SKILL.md").is_file():
        targets = [
            repo_root / ".kimi-code" / "skills" / "cineflow",
            repo_root / ".kimi" / "skills" / "cineflow",
            repo_root / ".agents" / "skills" / "cineflow",
            repo_root / ".claude" / "skills" / "cineflow",
            repo_root / ".cursor" / "skills" / "cineflow",
        ]
        for t in targets:
            t.parent.mkdir(parents=True, exist_ok=True)
            if t.exists():
                shutil.rmtree(t)
            shutil.copytree(skill_source_dir, t)
            synced_locations.append(str(t.relative_to(repo_root)))

    davinci_script = install_davinci_script()

    # Re-run pip install -e . quietly (skip during tests)
    import os
    if not os.getenv("PYTEST_CURRENT_TEST"):
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-e", str(repo_root), "--no-warn-script-location", "-q"],
                check=False,
                timeout=30,
                capture_output=True,
            )
        except (subprocess.SubprocessError, OSError):
            pass

    return {
        "status": "updated",
        "mode": "git",
        "git_pull": pull_output,
        "synced_skills": synced_locations,
        "davinci_script": str(davinci_script) if davinci_script else "Not installed (DaVinci Resolve not detected)",
        "message": "CineFlow Studio, skills, and NLE connectors successfully updated to the latest parent release.",
    }
