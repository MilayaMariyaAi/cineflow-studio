"""cineflow-setup: install the CineFlow skill into IDE folders, write MCP
configs, and print the local GPU profile (Studio 1d, ticket #685).

Distribution without GitHub: the package installs from PyPI; the skill comes
from the package data (cineflow_studio/skill/cineflow), not from any repo.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

SKILL_SRC = Path(__file__).resolve().parent / "skill" / "cineflow"

# IDE skill target directories (each receives the 'cineflow' skill folder)
IDE_SKILL_PARENTS = [
    ".agents/skills",
    ".claude/skills",
    ".kimi/skills",
    ".kimi-code/skills",
    ".cursor/skills",
]

MCP_CONFIG_FILES = [
    ".cursor/mcp.json",
    ".claude/mcp.json",
    ".kimi/mcp.json",
    ".kimi-code/mcp.json",
    ".trae/mcp.json",
]


def install_skill(repo_root: Path) -> list[str]:
    installed: list[str] = []
    for parent in IDE_SKILL_PARENTS:
        dest = repo_root / parent / "cineflow"
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(SKILL_SRC, dest)
        installed.append(str(dest.relative_to(repo_root)))
    return installed


def write_mcp_configs(repo_root: Path, command: str = "uvx", args: list[str] | None = None) -> list[str]:
    server_entry = {"cineflow": {"command": command, "args": args or ["cineflow-studio"]}}
    written: list[str] = []
    preserved: list[str] = []
    for rel in MCP_CONFIG_FILES:
        path = repo_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        config: dict = {}
        if path.is_file():
            try:
                config = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                config = {}
        servers = config.get("mcpServers")
        if not isinstance(servers, dict):
            servers = {}
        existing = servers.get("cineflow")
        if isinstance(existing, dict) and "url" in existing:
            # D4 (#754): a configured HTTP+Bearer setup is the user's working
            # config — never clobber it back to stdio. Skip and note.
            preserved.append(rel)
            continue
        servers.update(server_entry)
        config["mcpServers"] = servers
        path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written.append(rel)
    if preserved:
        print(f"   preserved HTTP config in: {', '.join(preserved)}")
    return written


def gpu_profile_line() -> str:
    try:
        from cineflow_studio.installer.hardware import inspect_hardware

        hw = inspect_hardware()
        return (
            f"GPU: {hw.gpu_name or 'None (CPU only)'} | VRAM: {hw.vram_gb:.1f} GB"
            f" | profile: {hw.recommended_profile}"
        )
    except Exception as exc:  # noqa: BLE001 — hardware detection must never fail the setup
        return f"GPU profile unavailable ({exc})"


def comfy_hint() -> str:
    if shutil.which("nvidia-smi") is None:
        return "No NVIDIA GPU detected: use community mode with a cloud render backend or a CPU-only preview."
    return "Local ComfyUI renders on your GPU: the model installer and launcher scripts are in the package bin/."


def write_bridge_scripts(repo_root: Path) -> list[str]:
    """One-click bridge launchers next to the mcp.json files (#756): the user
    double-clicks and the HTTP MCP stays alive; no manual uvx in a console."""
    uvx_cmd = (
        'uvx --from git+https://github.com/MilayaMariyaAi/cineflow-studio cineflow-mcp-http'
    )
    written: list[str] = []
    bat = repo_root / "start_mcp_bridge.bat"
    bat.write_text(
        "@echo off\r\n"
        "title CineFlow MCP bridge (keep this window open)\r\n"
        f"{uvx_cmd}\r\n"
        "pause\r\n",
        encoding="utf-8",
    )
    written.append(str(bat))
    sh = repo_root / "start_mcp_bridge.sh"
    sh.write_text(
        "#!/usr/bin/env bash\n"
        "# CineFlow MCP bridge (keep this terminal open)\n"
        f"{uvx_cmd}\n",
        encoding="utf-8",
    )
    try:
        sh.chmod(0o755)
    except OSError:
        pass
    written.append(str(sh))
    return written


def main() -> int:
    # Emoji output crashes a cp1252 Windows console (and `python -I` ignores
    # PYTHONIOENCODING) — reconfigure before the first print (#752).
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    repo_root = Path.cwd()
    print("🎬 CineFlow Studio setup")
    print(f"   Workspace: {repo_root}")

    installed = install_skill(repo_root)
    print("🧠 Skill installed:")
    for rel in installed:
        print(f"   {rel}")

    written = write_mcp_configs(repo_root)
    print("🔌 MCP configs written:")
    for rel in written:
        print(f"   {rel}")

    bridge = write_bridge_scripts(repo_root)
    print("🌐 MCP bridge launchers:")
    for rel in bridge:
        print(f"   {rel}")

    print(f"🖥️  {gpu_profile_line()}")
    print(f"💡 {comfy_hint()}")

    try:
        from cineflow_studio.installer.runner import (
            generate_dependency_install_script,
            generate_launch_script,
        )

        comfy_dir = Path("ComfyUI")
        s1 = generate_dependency_install_script(comfy_dir)
        s2 = generate_launch_script(comfy_dir)
        print(f"📦 Model installer: {s1}")
        print(f"🚀 ComfyUI launcher: {s2}")
    except Exception as exc:  # noqa: BLE001 — optional step
        print(f"   (ComfyUI launcher generation skipped: {exc})")

    print("✅ Done. Open your IDE and start: 'Сделай проект из этого сценария.'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
