"""DaVinci Resolve MCP Connector and Bi-directional Live Link.

Provides:
- Direct timeline synchronization with DaVinci Resolve via DaVinciResolveScript API.
- Fallback FCPXML 1.10 export with roundtrip metadata.
- Auto-installation of 'CineFlow_Edit_in_ComfyUI.py' script inside DaVinci Resolve's Edit menu.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger("cineflow_studio.mcp.davinci")

DAVINCI_SCRIPT_CONTENT = '''#!/usr/bin/env python3
"""CineFlow DaVinci Resolve Live Action: Edit in ComfyUI / Regenerate Shot.

Discovered in DaVinci Resolve under:
Workspace -> Scripts -> Edit -> CineFlow_Edit_in_ComfyUI

Inspects the selected clip on the timeline, reads its sidecar .cineflow.json,
and opens the exact ComfyUI workflow / prompt for revision.
"""
import sys
import os
import re
import json
import webbrowser
from pathlib import Path

def find_resolve():
    try:
        import DaVinciResolveScript as bmd
        return bmd.scriptapp("Resolve")
    except ImportError:
        if sys.platform == "darwin":
            sys.path.append("/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules")
        elif sys.platform == "win32":
            sys.path.append(os.path.expandvars(r"%PROGRAMDATA%\\Blackmagic Design\\DaVinci Resolve\\Support\\Developer\\Scripting\\Modules"))
        try:
            import DaVinciResolveScript as bmd
            return bmd.scriptapp("Resolve")
        except Exception:
            return None

resolve = find_resolve()
if not resolve:
    print("[CineFlow] Could not connect to DaVinci Resolve.")
    sys.exit(0)

project = resolve.GetProjectManager().GetCurrentProject()
if not project:
    print("[CineFlow] No active project.")
    sys.exit(0)

timeline = project.GetCurrentTimeline()
target_url = "http://127.0.0.1:8721/lab/"
sidecar_data = None

if timeline:
    # 1. Try to inspect the currently selected clip on the timeline
    try:
        current_item = timeline.GetCurrentVideoItem()
        if current_item:
            media_item = current_item.GetMediaPoolItem()
            if media_item:
                file_path_str = media_item.GetClipProperty("File Path")
                if file_path_str:
                    media_path = Path(file_path_str)
                    sidecar_file = media_path.with_suffix(".cineflow.json")
                    if sidecar_file.exists():
                        sidecar_data = json.loads(sidecar_file.read_text(encoding="utf-8"))
                        print(f"[CineFlow] Found sidecar metadata for clip: {media_path.name}")
    except Exception as exc:
        print(f"[CineFlow] Note inspecting video item: {exc}")

    # 2. Extract URL from sidecar or timeline markers
    if sidecar_data:
        comfy_url = sidecar_data.get("comfy_url", "http://127.0.0.1:8188")
        project_id = sidecar_data.get("project_id", "")
        shot_id = sidecar_data.get("shot_id", "")
        workflow_path = sidecar_data.get("workflow_path", "")
        if project_id and shot_id:
            target_url = f"http://127.0.0.1:8721/lab/projects/{project_id}/shots/{shot_id}"
        elif workflow_path:
            target_url = f"{comfy_url}/?load={workflow_path}"
        else:
            target_url = comfy_url
    else:
        markers = timeline.GetMarkers() or {}
        for frame_id, marker in markers.items():
            note = marker.get("note", "")
            match = re.search(r"https?://127\\.0\\.0\\.1:\\d+/[^\\s,;]+", note)
            if match:
                target_url = match.group(0)
                break

print(f"[CineFlow] Opening ComfyUI / CineFlow Studio: {target_url}")
webbrowser.open(target_url)
'''


def get_davinci_scripts_edit_dir() -> Path | None:
    """Returns the user scripts directory for DaVinci Resolve Edit page."""
    if sys.platform == "darwin":
        path = Path.home() / "Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Edit"
    elif sys.platform == "win32":
        appdata = os.getenv("APPDATA")
        if not appdata:
            return None
        path = Path(appdata) / "Blackmagic Design/DaVinci Resolve/Support/Fusion/Scripts/Edit"
    else:  # Linux
        path = Path.home() / ".local/share/DaVinciResolve/Fusion/Scripts/Edit"

    return path


def install_davinci_script() -> Path | None:
    """Installs CineFlow_Edit_in_ComfyUI.py into DaVinci Resolve's Scripts/Edit menu."""
    scripts_dir = get_davinci_scripts_edit_dir()
    if not scripts_dir:
        return None
    try:
        scripts_dir.mkdir(parents=True, exist_ok=True)
        script_file = scripts_dir / "CineFlow_Edit_in_ComfyUI.py"
        script_file.write_text(DAVINCI_SCRIPT_CONTENT, encoding="utf-8")
        script_file.chmod(0o755)
        return script_file
    except OSError:
        return None


def get_resolve_api():
    """Attempts to connect to live running DaVinci Resolve."""
    try:
        import DaVinciResolveScript as bmd
        return bmd.scriptapp("Resolve")
    except ImportError:
        if sys.platform == "darwin":
            ext_path = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting/Modules"
            if ext_path not in sys.path and os.path.exists(ext_path):
                sys.path.append(ext_path)
        elif sys.platform == "win32":
            win_path = os.path.expandvars(r"%PROGRAMDATA%\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\Modules")
            if win_path not in sys.path and os.path.exists(win_path):
                sys.path.append(win_path)
        try:
            import DaVinciResolveScript as bmd
            return bmd.scriptapp("Resolve")
        except Exception:  # noqa: BLE001
            return None


def sync_to_davinci(project_id: str, timeline_name: str | None = None, install_action: bool = True) -> dict[str, Any]:
    """Synchronizes CineFlow project with DaVinci Resolve."""
    script_installed_path = None
    if install_action:
        script_installed_path = install_davinci_script()

    resolve = get_resolve_api()
    project_dir = Path("storage/projects") / project_id
    clips_dir = project_dir / "clips"
    export_dir = project_dir / "export"
    export_dir.mkdir(parents=True, exist_ok=True)

    # Gather rendered media clips (from clips/ and scenes/*/video/)
    clips_set = set()
    if clips_dir.exists():
        clips_set.update(clips_dir.glob("*.mp4"))
    for scene_video_dir in project_dir.glob("scenes/*/video"):
        clips_set.update(scene_video_dir.glob("*.mp4"))

    clips = sorted(clips_set, key=lambda p: p.name)

    timeline_title = timeline_name or f"CineFlow_{project_id}"

    # Try Live API first
    if resolve:
        try:
            pm = resolve.GetProjectManager()
            cur_project = pm.GetCurrentProject()
            if not cur_project:
                cur_project = pm.CreateProject(timeline_title) or pm.GetCurrentProject()

            if cur_project:
                media_pool = cur_project.GetMediaPool()
                root_folder = media_pool.GetRootFolder()
                # Create CineFlow Bin
                cineflow_bin = None
                for subfolder in root_folder.GetSubFolderList() or []:
                    if subfolder.GetName() == "CineFlow":
                        cineflow_bin = subfolder
                        break
                if not cineflow_bin:
                    cineflow_bin = media_pool.AddSubFolder(root_folder, "CineFlow")

                media_pool.SetCurrentFolder(cineflow_bin)
                clip_paths = [str(c.resolve()) for c in clips]
                imported_items = media_pool.ImportMedia(clip_paths) if clip_paths else []

                # Create timeline from clips if items exist
                timeline = None
                if imported_items:
                    timeline = media_pool.CreateTimelineFromClips(timeline_title, imported_items)
                    if timeline:
                        # Add markers with ComfyUI deep links
                        for idx, item in enumerate(imported_items, start=1):
                            frame_pos = (idx - 1) * 125  # ~5 sec at 25 fps
                            edit_url = f"http://127.0.0.1:8721/lab/projects/{project_id}/shots/{idx}"
                            timeline.AddMarker(
                                frame_pos,
                                "Cyan",
                                f"Shot {idx}",
                                f"comfyEdit={edit_url}",
                                1,
                            )

                return {
                    "status": "synced",
                    "mode": "live_api",
                    "project_id": project_id,
                    "timeline_name": timeline_title,
                    "clips_imported": len(imported_items),
                    "davinci_project": cur_project.GetName(),
                    "davinci_script_installed": str(script_installed_path) if script_installed_path else None,
                    "action_menu": "Workspace -> Scripts -> Edit -> CineFlow_Edit_in_ComfyUI",
                    "message": "Project synchronized directly into running DaVinci Resolve session.",
                }
        except Exception as exc:  # noqa: BLE001
            logger.debug("Live DaVinci API sync failed, falling back to FCPXML: %s", exc)

    # Fallback to FCPXML 1.10 file generation
    fcpxml_path = export_dir / "timeline_davinci.fcpxml"
    fcpxml_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE fcpxml>
<fcpxml version="1.10">
    <resources>
        <format id="r1" name="FFVideoFormat1080p25" frameDuration="1/25s" width="1080" height="1920"/>
    </resources>
    <library>
        <event name="CineFlow {project_id}">
            <project name="{timeline_title}">
                <sequence format="r1" duration="{len(clips)*5}s">
                    <spine>
'''
    for idx, c in enumerate(clips, start=1):
        comfy_url = f"http://127.0.0.1:8721/lab/projects/{project_id}/shots/{idx}"
        fcpxml_content += f'''                        <asset-clip name="{c.name}" offset="{(idx-1)*5}s" duration="5s" format="r1">
                            <note>shotId=shot_{idx:02d}; comfyEdit={comfy_url}</note>
                            <marker start="0s" duration="1/25s" value="Shot {idx}" note="comfyEdit={comfy_url}"/>
                        </asset-clip>
'''
    fcpxml_content += '''                    </spine>
                </sequence>
            </project>
        </event>
    </library>
</fcpxml>
'''
    fcpxml_path.write_text(fcpxml_content, encoding="utf-8")

    return {
        "status": "exported",
        "mode": "fcpxml",
        "project_id": project_id,
        "timeline_name": timeline_title,
        "clips_count": len(clips),
        "fcpxml_path": str(fcpxml_path),
        "davinci_script_installed": str(script_installed_path) if script_installed_path else None,
        "import_instructions": "In DaVinci Resolve: File -> Import -> Timeline -> select timeline_davinci.fcpxml.",
        "action_menu": "Select clip on timeline -> Workspace -> Scripts -> Edit -> CineFlow_Edit_in_ComfyUI to open in ComfyUI.",
    }
