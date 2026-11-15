# DaVinci Resolve Live Link & NLE Integration Reference

This document describes the bi-directional round-trip integration between CineFlow and Non-Linear Editors (NLEs), focusing on DaVinci Resolve Studio.

---

## 1. Bi-Directional Workflow Overview

```text
CineFlow (Director Agent)
       │
       ▼ (cineflow_export_mp4 / cineflow_davinci_sync)
Timeline + Clips + Sidecar .cineflow.json
       │
       ▼
DaVinci Resolve Studio (Timeline)
       │ (User selects clip, clicks "Edit in ComfyUI")
       ▼
ComfyUI / CineFlow Lab (Reopens exact prompt, seed & nodes)
       │ (User tweaks parameters and re-renders)
       ▼
DaVinci Resolve Auto-Refresh (Takes replacement)
```

---

## 2. DaVinciResolveScript API Integration

CineFlow communicates with DaVinci Resolve Studio through its official Python API:
- **Import:** `import DaVinciResolveScript as dvr_script`
- **Resolve Instance:** `resolve = dvr_script.scriptapp("Resolve")`
- **Project Manager:** `project_manager = resolve.GetProjectManager()`
- **Media Pool:** `media_pool = project.GetMediaPool()`

When `cineflow_davinci_sync` is executed:
1. CineFlow connects to the active DaVinci Resolve project (or creates one matching the CineFlow project title).
2. Media bins (`Materials/`, `Audio/`, `Video/`) are populated with generated assets.
3. A sequence timeline is created with proper video tracks (Video 1: Visual Takes) and audio tracks (Audio 1: Dialogue, Audio 2: Music/SFX).
4. **Timeline Markers:** Cyan markers are placed at the head of every shot containing shot ID, take number, and deep links.

---

## 3. Sidecar Metadata Format (`.cineflow.json`)

Alongside every generated video take `{shot_id}.mp4`, CineFlow generates `{shot_id}.cineflow.json`:

```json
{
  "version": "1.0",
  "project_id": "cyberpunk_short",
  "scene_id": "scene_02",
  "shot_id": "shot_04",
  "take_id": 1,
  "created_at": "2026-11-12T10:30:00Z",
  "engine": "comfyui",
  "model": "ltx-video-2b-v0.9.5-fp8.safetensors",
  "seed": 89237194,
  "prompt": "Cinematic 35mm, rainy neon street, close-up of <Subject 1>, vibrant cyan rim light.",
  "workflow_path": "scenes/scene_02/workflows/shot_04.comfy.json",
  "comfy_url": "http://127.0.0.1:8188",
  "duration_seconds": 5.0,
  "fps": 24.0,
  "resolution": [1280, 720]
}
```

---

## 4. The "Edit in ComfyUI" Menu Script

To enable 1-click roundtrip editing, CineFlow installs a script into DaVinci Resolve:
- **Mac path:** `~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Edit/CineFlow_Edit_in_ComfyUI.py`
- **Windows path:** `%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Edit\CineFlow_Edit_in_ComfyUI.py`
- **Linux path:** `~/.local/share/DaVinciResolve/Fusion/Scripts/Edit/CineFlow_Edit_in_ComfyUI.py`

### Script Logic:
1. Gets the currently selected clip on the active timeline.
2. Locates the companion `.cineflow.json` sidecar next to the clip's source file.
3. Reads `workflow_path` and `comfy_url`.
4. Opens the browser at `http://127.0.0.1:8188` (or CineFlow Lab) with the exact prompt and seed pre-loaded.

---

## 5. Offline Fallback: FCPXML 1.10 Export

For systems without DaVinci Resolve running or for third-party NLEs (Adobe Premiere Pro, Final Cut Pro):
- CineFlow exports `export/timeline_davinci.fcpxml`.
- Adheres to Apple Final Cut Pro XML 1.10 specification.
- Embeds shot markers, duration cuts, dialogue audio sync, and clip metadata tags.
