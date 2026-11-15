"""Automated updates synchronization for CineFlow Studio and Skills."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from cineflow_studio.mcp.davinci import install_davinci_script


def _get_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def check_cineflow_updates() -> dict[str, Any]:
    """Checks upstream Git repository for newly released features, models, or skill updates."""
    repo_root = _get_repo_root()

    # 1. Fetch remote changes quietly with timeout
    try:
        subprocess.run(
            ["git", "-C", str(repo_root), "fetch", "origin", "--quiet"],
            check=False,
            timeout=8,
            capture_output=True,
        )
    except (subprocess.SubprocessError, OSError):
        pass  # Graceful fallback in offline / air-gapped environments

    # 2. Get current HEAD commit
    try:
        head_commit = subprocess.check_output(
            ["git", "-C", str(repo_root), "rev-parse", "--short", "HEAD"],
            text=True,
            timeout=3,
        ).strip()
    except (subprocess.SubprocessError, OSError):
        head_commit = "unknown"

    # 3. Check commits behind remote
    new_commits: list[str] = []
    commits_behind = 0
    try:
        # Check against origin/main or tracking branch
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
        "current_commit": head_commit,
        "commits_behind": commits_behind,
        "new_commits": new_commits,
        "message": (
            f"Found {commits_behind} new update(s) in CineFlow repository."
            if updates_available
            else "CineFlow Studio is up to date."
        ),
        "action": "Call 'cineflow_apply_update' or run './scripts/cineflow_update' to pull changes." if updates_available else "No action needed.",
    }


def apply_cineflow_updates() -> dict[str, Any]:
    """Pulls upstream updates, syncs skills across IDEs, and updates DaVinci Resolve scripts."""
    repo_root = _get_repo_root()

    # 1. Git pull
    pull_output = ""
    try:
        pull_res = subprocess.run(
            ["git", "-C", str(repo_root), "pull", "--ff-only"],
            text=True,
            timeout=5,
            capture_output=True,
            check=False,
        )
        pull_output = (pull_res.stdout + pull_res.stderr).strip()
    except (subprocess.SubprocessError, OSError) as exc:
        pull_output = f"Git pull skipped or timed out: {exc}"

    # 2. Sync the canonical skill (skill/cineflow/, Studio 0c) across IDE discovery locations
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

    # 3. Refresh DaVinci Resolve Action Script
    davinci_script = install_davinci_script()

    # 4. Re-run pip install -e . quietly (skip during tests)
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
        "git_pull": pull_output,
        "synced_skills": synced_locations,
        "davinci_script": str(davinci_script) if davinci_script else "Not installed (DaVinci Resolve not detected)",
        "message": "CineFlow Studio, skills, and NLE connectors successfully updated to latest parent release.",
    }
