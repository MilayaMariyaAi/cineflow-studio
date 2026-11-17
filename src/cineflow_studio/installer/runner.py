"""ComfyUI supervised launch script generator, disk cleanup, and health audit."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from cineflow_studio.installer.hardware import inspect_hardware
from cineflow_studio.installer.manifest import (
    CUSTOM_NODES_CATALOG,
    MODELS_CATALOG,
    get_weights_for_profile,
)

PROFILE_FLAGS = {
    "rtx_24gb": "--highvram --gpu-only --listen 127.0.0.1 --port 8188",
    "rtx_16gb": "--fp8_e4m3fn-unet --lowvram --listen 127.0.0.1 --port 8188",
    "rtx_12gb": "--lowvram --disable-xformers --listen 127.0.0.1 --port 8188",
    "apple_silicon": "--listen 127.0.0.1 --port 8188",
    "cloud_only": "",
}


def generate_launch_script(comfy_dir: Path, profile_name: str | None = None) -> Path:
    """Generates the optimal ComfyUI launch script with hardware flags."""
    comfy_dir = Path(comfy_dir)
    comfy_dir.mkdir(parents=True, exist_ok=True)
    hw = inspect_hardware(comfy_dir)
    active_profile = profile_name or hw.recommended_profile
    flags = PROFILE_FLAGS.get(active_profile, hw.recommended_flags)

    if sys.platform == "win32":
        script_path = comfy_dir / "run_comfy_cineflow.bat"
        content = f"""@echo off
title CineFlow ComfyUI Supervised Runner [{active_profile}]
cd /d "%~dp0"
echo [CineFlow] Launching ComfyUI with {active_profile} profile...
call venv\\Scripts\\activate.bat 2>nul || python -m venv venv && call venv\\Scripts\\activate.bat
python main.py {flags}
pause
"""
    else:
        script_path = comfy_dir / "run_comfy_cineflow.sh"
        content = f"""#!/bin/sh
# CineFlow ComfyUI Supervised Runner [{active_profile}]
set -e
cd "$(dirname "$0")"
echo "[CineFlow] Launching ComfyUI with {active_profile} profile..."
if [ -d "venv" ]; then
    . venv/bin/activate
fi
exec python3 main.py {flags}
"""

    script_path.write_text(content, encoding="utf-8")
    script_path.chmod(0o755)
    return script_path


def cleanup_latents_cache(comfy_dir: Path) -> dict[str, Any]:
    """Cleans up temporary latent files and preview artifacts (#608)."""
    comfy_path = Path(comfy_dir)
    latents_dir = comfy_path / "output" / "latents"
    temp_dir = comfy_path / "temp"

    cleaned_count = 0
    freed_bytes = 0

    for d in (latents_dir, temp_dir):
        if d.is_dir():
            for f in d.glob("*"):
                try:
                    if f.is_file():
                        freed_bytes += f.stat().st_size
                        f.unlink()
                        cleaned_count += 1
                except OSError:
                    pass

    return {
        "status": "cleaned",
        "files_removed": cleaned_count,
        "freed_mb": round(freed_bytes / (1024**2), 2),
    }


def audit_comfy_installation(comfy_dir: Path | None = None) -> dict[str, Any]:
    """Checks the status of local ComfyUI installation, models, and custom nodes."""
    target = Path(comfy_dir or os.getenv("COMFYUI_DIR", "ComfyUI"))
    is_installed = (target / "main.py").is_file()

    hw = inspect_hardware(target if target.exists() else None)
    expected_weights = get_weights_for_profile(hw.recommended_profile)

    installed_weights: list[str] = []
    missing_weights: list[str] = []

    for w in expected_weights:
        model_file = target / w.local_relative_path
        if model_file.is_file():
            installed_weights.append(w.name)
        else:
            missing_weights.append(w.name)

    total_expected = len(expected_weights)
    readiness = round((len(installed_weights) / max(1, total_expected)) * 100) if is_installed else 0

    return {
        "comfy_dir": str(target.resolve()),
        "is_comfy_installed": is_installed,
        "hardware_profile": hw.to_dict(),
        "readiness_percent": readiness,
        "installed_weights": installed_weights,
        "missing_weights": missing_weights,
        "total_required_weights": total_expected,
    }


def install_custom_node(comfy_dir: Path, node_name: str, git_url: str | None = None) -> dict[str, Any]:
    """Installs or updates a ComfyUI custom node from a Git repository."""
    comfy_dir = Path(comfy_dir)
    custom_nodes_dir = comfy_dir / "custom_nodes"
    custom_nodes_dir.mkdir(parents=True, exist_ok=True)

    # Find git url from catalog if not provided
    resolved_url = git_url
    if not resolved_url:
        for node in CUSTOM_NODES_CATALOG:
            if node["name"].lower() == node_name.lower():
                resolved_url = node["git_url"]
                node_name = node["name"]
                break

    if not resolved_url:
        raise ValueError(f"Custom node '{node_name}' not found in catalog and no git_url provided.")

    target_dir = custom_nodes_dir / node_name
    action = "cloned"
    if target_dir.is_dir() and (target_dir / ".git").is_dir():
        action = "updated"
        subprocess.run(["git", "-C", str(target_dir), "pull"], check=False, timeout=60, capture_output=True)
    else:
        subprocess.run(["git", "clone", resolved_url, str(target_dir)], check=False, timeout=120, capture_output=True)

    # Check for requirements.txt
    reqs_file = target_dir / "requirements.txt"
    pip_installed = False
    if reqs_file.is_file():
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(reqs_file)], check=False, timeout=180, capture_output=True)
        pip_installed = True

    return {
        "status": action,
        "node_name": node_name,
        "git_url": resolved_url,
        "installed_to": str(target_dir.resolve()),
        "requirements_installed": pip_installed,
    }


def download_model(
    comfy_dir: Path,
    model_name: str,
    mirror: str = "huggingface",
    execute_download: bool = False,
) -> dict[str, Any]:
    """Resolves destination and constructs/executes download command for a model weight."""
    comfy_dir = Path(comfy_dir)
    target_model = None
    for m in MODELS_CATALOG:
        if m.name.lower() == model_name.lower() or m.hf_filename.lower() == model_name.lower():
            target_model = m
            break

    if not target_model:
        raise ValueError(f"Model '{model_name}' not found in CineFlow models catalog.")

    dest_file = comfy_dir / target_model.local_relative_path
    dest_file.parent.mkdir(parents=True, exist_ok=True)

    url = target_model.get_url(mirror)
    curl_cmd = f"curl -L -C - -o '{dest_file}' '{url}'"

    already_downloaded = dest_file.is_file() and dest_file.stat().st_size > 1024 * 1024

    if execute_download and not already_downloaded:
        subprocess.run(
            ["curl", "-L", "-C", "-", "-o", str(dest_file), url],
            check=False,
            timeout=600,
            capture_output=True,
        )
        already_downloaded = dest_file.is_file()

    return {
        "status": "ready" if already_downloaded else "pending",
        "model_name": target_model.name,
        "category": target_model.category,
        "file_path": str(dest_file.resolve()),
        "size_gb": target_model.size_gb,
        "download_url": url,
        "mirror": mirror,
        "curl_command": curl_cmd,
        "already_downloaded": already_downloaded,
    }


def generate_dependency_install_script(
    comfy_dir: Path,
    profile_name: str | None = None,
    mirror: str = "huggingface",
) -> Path:
    """Generates an all-in-one bash/bat installer script with git clones and resumable model downloads."""
    comfy_dir = Path(comfy_dir)
    comfy_dir.mkdir(parents=True, exist_ok=True)

    hw = inspect_hardware(comfy_dir)
    active_profile = profile_name or hw.recommended_profile
    weights = get_weights_for_profile(active_profile)

    if sys.platform == "win32":
        script_path = comfy_dir / "install_cineflow_models.bat"
        lines = [
            "@echo off",
            f"title CineFlow Model & Custom Node Installer [{active_profile}]",
            "cd /d \"%~dp0\"",
            "echo [CineFlow] Installing custom nodes and models...",
            "mkdir custom_nodes 2>nul",
        ]
        for node in CUSTOM_NODES_CATALOG:
            lines.append(f"if not exist \"custom_nodes\\{node['name']}\" git clone {node['git_url']} \"custom_nodes\\{node['name']}\"")
        for w in weights:
            rel_dir = Path(w.local_relative_path).parent
            lines.append(f"mkdir \"{rel_dir}\" 2>nul")
            lines.append(f"curl -L -C - -o \"{w.local_relative_path}\" \"{w.get_url(mirror)}\"")
        lines.append("echo [CineFlow] All models and custom nodes provisioned successfully!")
        lines.append("pause")
        content = "\r\n".join(lines) + "\r\n"
    else:
        script_path = comfy_dir / "install_cineflow_models.sh"
        lines = [
            "#!/bin/sh",
            f"# CineFlow Model & Custom Node Installer [{active_profile}]",
            "set -e",
            "cd \"$(dirname \"$0\")\"",
            "echo \"[CineFlow] Installing custom nodes and models...\"",
            "mkdir -p custom_nodes",
        ]
        for node in CUSTOM_NODES_CATALOG:
            lines.append(f"if [ ! -d \"custom_nodes/{node['name']}\" ]; then")
            lines.append(f"    git clone \"{node['git_url']}\" \"custom_nodes/{node['name']}\"")
            lines.append("fi")
        for w in weights:
            rel_dir = Path(w.local_relative_path).parent
            lines.append(f"mkdir -p \"{rel_dir}\"")
            lines.append(f"echo \"Downloading {w.name} ({w.size_gb} GB)...\"")
            lines.append(f"curl -L -C - -o \"{w.local_relative_path}\" \"{w.get_url(mirror)}\"")
        lines.append("echo \"[CineFlow] All models and custom nodes provisioned successfully!\"")
        content = "\n".join(lines) + "\n"

    script_path.write_text(content, encoding="utf-8")
    script_path.chmod(0o755)
    return script_path
