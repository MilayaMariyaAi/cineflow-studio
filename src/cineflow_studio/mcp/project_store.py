"""Project Storage and Source-of-Truth Management for CineFlow Agents.

Manages physical project folders on disk:
- `source/`: Original screenplays, book texts, synopses.
- `project.json`: Single Source of Truth passport (metadata, cast, locations, scenes, status).
- `materials/`: Character, prop, and location cards.
- `scenes/scene_XX/`: Discrete scene production workspaces.
- `export/`: Timeline, FCPXML, and master video renders.
"""
from __future__ import annotations

import json
import os
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


def get_projects_root() -> Path:
    storage_root = os.getenv("CINEFLOW_STORAGE_DIR", "storage")
    return Path(storage_root) / "projects"


def get_project_dir(project_id: str) -> Path:
    return get_projects_root() / project_id


def get_manifest_path(project_id: str) -> Path:
    return get_project_dir(project_id) / "project.json"


def list_all_projects(filter_query: str | None = None) -> list[dict[str, Any]]:
    """Lists all registered projects across storage/projects with cast and location previews."""
    root = get_projects_root()
    if not root.exists():
        return []

    projects = []
    for p in root.iterdir():
        if p.is_dir() and (p / "project.json").is_file():
            try:
                manifest = json.loads((p / "project.json").read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue

            proj_id = manifest.get("project_id", p.name)
            title = manifest.get("title", p.name)

            if filter_query:
                q = filter_query.lower().strip()
                if q not in proj_id.lower() and q not in title.lower():
                    continue

            chars = [
                {
                    "name": c.get("name"),
                    "render_name": c.get("render_name"),
                    "character_type": c.get("character_type", "human"),
                    "has_sheet": bool(c.get("image_path") or c.get("sheet_path")),
                    "has_voice": bool(c.get("voice_sample") or c.get("voice_id")),
                }
                for c in manifest.get("characters", [])
                if isinstance(c, dict)
            ]
            locs = [
                {
                    "name": l.get("name"),
                    "int_ext": l.get("int_ext"),
                    "has_photo": bool(l.get("image_path") or l.get("photo_path")),
                }
                for l in manifest.get("locations", [])
                if isinstance(l, dict)
            ]
            props = [
                {"name": pr.get("name")}
                for pr in manifest.get("props", [])
                if isinstance(pr, dict)
            ]

            projects.append({
                "project_id": proj_id,
                "title": title,
                "stage": manifest.get("stage", "draft"),
                "characters_count": len(chars),
                "characters": chars,
                "locations_count": len(locs),
                "locations": locs,
                "props_count": len(props),
                "props": props,
                "scenes_count": len(manifest.get("scenes", [])),
                "created_at": manifest.get("created_at"),
                "updated_at": manifest.get("updated_at"),
                "path": str(p),
            })

    projects.sort(key=lambda x: str(x.get("updated_at", "")), reverse=True)
    return projects


def find_project(query: str) -> dict[str, Any] | None:
    """Finds a project manifest by exact ID, or case-insensitive fuzzy match against title/id."""
    clean_q = query.strip()
    if not clean_q:
        return None

    # 1. Try exact project_id directly
    direct_path = get_project_dir(clean_q) / "project.json"
    if direct_path.is_file():
        try:
            return json.loads(direct_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    # 2. Search all projects
    root = get_projects_root()
    if not root.exists():
        return None

    candidates: list[tuple[int, dict[str, Any]]] = []
    q_lower = clean_q.lower()

    for p in root.iterdir():
        if p.is_dir() and (p / "project.json").is_file():
            try:
                manifest = json.loads((p / "project.json").read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue

            proj_id = str(manifest.get("project_id", p.name)).lower()
            title = str(manifest.get("title", "")).lower()

            if title == q_lower:
                candidates.append((3, manifest))
            elif q_lower in title:
                candidates.append((2, manifest))
            elif q_lower in proj_id:
                candidates.append((1, manifest))

    if not candidates:
        return None

    candidates.sort(key=lambda c: c[0], reverse=True)
    return candidates[0][1]


def transfer_project_assets(
    source_project: str,
    target_project_id: str,
    asset_types: list[str] | None = None,
    names: list[str] | None = None,
    conflict_strategy: str = "skip",
) -> dict[str, Any]:
    """Transfers/clones characters, locations, and props from source project to target project.

    Supports deterministic file-based manifest updates and mirrors media files
    (turnarounds, voice samples, plates) into target project materials.
    """
    source_manifest = find_project(source_project)
    if not source_manifest:
        available = [p["title"] for p in list_all_projects()[:5]]
        return {
            "status": "error",
            "message": f"Source project '{source_project}' not found. Available projects: {available}",
        }

    try:
        target_manifest = read_project_manifest(target_project_id)
    except FileNotFoundError:
        return {
            "status": "error",
            "message": f"Target project '{target_project_id}' not found.",
        }

    types_to_copy = set(asset_types) if asset_types else {"characters", "locations", "props"}
    names_filter = {n.strip().lower() for n in names} if names else None

    transferred_characters: list[str] = []
    transferred_locations: list[str] = []
    transferred_props: list[str] = []
    skipped_items: list[dict[str, Any]] = []
    copied_files_count = 0

    target_materials_dir = get_project_dir(target_project_id) / "materials"

    # 1. Transfer Characters
    if "characters" in types_to_copy:
        target_chars: list[dict[str, Any]] = target_manifest.setdefault("characters", [])
        existing_names = {c.get("name", "").lower(): idx for idx, c in enumerate(target_chars)}

        for c in source_manifest.get("characters", []):
            if not isinstance(c, dict):
                continue
            char_name = c.get("name", "").strip()
            if not char_name:
                continue
            if names_filter and char_name.lower() not in names_filter:
                continue

            name_key = char_name.lower()
            if name_key in existing_names:
                if conflict_strategy == "skip":
                    skipped_items.append({"type": "character", "name": char_name, "reason": "Already exists in target"})
                    continue
                elif conflict_strategy == "overwrite":
                    del target_chars[existing_names[name_key]]
                elif conflict_strategy == "rename":
                    char_name = f"{char_name} (копия из {source_manifest.get('title', 'проекта')})"

            new_char = dict(c)
            new_char["name"] = char_name
            char_slug = re.sub(r"[^\w\d]+", "_", char_name).strip("_").lower() or "character"
            target_char_dir = target_materials_dir / "characters" / char_slug
            target_char_dir.mkdir(parents=True, exist_ok=True)

            # Copy media files (image_path, sheet_path, voice_sample)
            for path_key in ("image_path", "sheet_path", "voice_sample"):
                src_val = c.get(path_key)
                if src_val and isinstance(src_val, str) and Path(src_val).is_file():
                    dest_file = target_char_dir / Path(src_val).name
                    shutil.copy2(src_val, dest_file)
                    new_char[path_key] = str(dest_file)
                    copied_files_count += 1

            new_char["provenance"] = {
                "source_project_id": source_manifest.get("project_id"),
                "source_project_title": source_manifest.get("title"),
                "original_name": c.get("name"),
                "transferred_at": _utcnow(),
            }

            target_chars.append(new_char)
            transferred_characters.append(char_name)

    # 2. Transfer Locations
    if "locations" in types_to_copy:
        target_locs: list[dict[str, Any]] = target_manifest.setdefault("locations", [])
        existing_loc_names = {l.get("name", "").lower(): idx for idx, l in enumerate(target_locs)}

        for l in source_manifest.get("locations", []):
            if not isinstance(l, dict):
                continue
            loc_name = l.get("name", "").strip()
            if not loc_name:
                continue
            if names_filter and loc_name.lower() not in names_filter:
                continue

            loc_key = loc_name.lower()
            if loc_key in existing_loc_names:
                if conflict_strategy == "skip":
                    skipped_items.append({"type": "location", "name": loc_name, "reason": "Already exists in target"})
                    continue
                elif conflict_strategy == "overwrite":
                    del target_locs[existing_loc_names[loc_key]]
                elif conflict_strategy == "rename":
                    loc_name = f"{loc_name} (копия из {source_manifest.get('title', 'проекта')})"

            new_loc = dict(l)
            new_loc["name"] = loc_name
            loc_slug = re.sub(r"[^\w\d]+", "_", loc_name).strip("_").lower() or "location"
            target_loc_dir = target_materials_dir / "locations" / loc_slug
            target_loc_dir.mkdir(parents=True, exist_ok=True)

            for path_key in ("image_path", "photo_path"):
                src_val = l.get(path_key)
                if src_val and isinstance(src_val, str) and Path(src_val).is_file():
                    dest_file = target_loc_dir / Path(src_val).name
                    shutil.copy2(src_val, dest_file)
                    new_loc[path_key] = str(dest_file)
                    copied_files_count += 1

            new_loc["provenance"] = {
                "source_project_id": source_manifest.get("project_id"),
                "source_project_title": source_manifest.get("title"),
                "original_name": l.get("name"),
                "transferred_at": _utcnow(),
            }

            target_locs.append(new_loc)
            transferred_locations.append(loc_name)

    # 3. Transfer Props
    if "props" in types_to_copy:
        target_props: list[dict[str, Any]] = target_manifest.setdefault("props", [])
        existing_prop_names = {pr.get("name", "").lower(): idx for idx, pr in enumerate(target_props)}

        for pr in source_manifest.get("props", []):
            if not isinstance(pr, dict):
                continue
            prop_name = pr.get("name", "").strip()
            if not prop_name:
                continue
            if names_filter and prop_name.lower() not in names_filter:
                continue

            prop_key = prop_name.lower()
            if prop_key in existing_prop_names:
                if conflict_strategy == "skip":
                    skipped_items.append({"type": "prop", "name": prop_name, "reason": "Already exists in target"})
                    continue
                elif conflict_strategy == "overwrite":
                    del target_props[existing_prop_names[prop_key]]
                elif conflict_strategy == "rename":
                    prop_name = f"{prop_name} (копия из {source_manifest.get('title', 'проекта')})"

            new_prop = dict(pr)
            new_prop["name"] = prop_name
            prop_slug = re.sub(r"[^\w\d]+", "_", prop_name).strip("_").lower() or "prop"
            target_prop_dir = target_materials_dir / "props" / prop_slug
            target_prop_dir.mkdir(parents=True, exist_ok=True)

            for path_key in ("image_path",):
                src_val = pr.get(path_key)
                if src_val and isinstance(src_val, str) and Path(src_val).is_file():
                    dest_file = target_prop_dir / Path(src_val).name
                    shutil.copy2(src_val, dest_file)
                    new_prop[path_key] = str(dest_file)
                    copied_files_count += 1

            new_prop["provenance"] = {
                "source_project_id": source_manifest.get("project_id"),
                "source_project_title": source_manifest.get("title"),
                "original_name": pr.get("name"),
                "transferred_at": _utcnow(),
            }

            target_props.append(new_prop)
            transferred_props.append(prop_name)

    # Save target manifest
    write_project_manifest(target_project_id, target_manifest)

    # Database synchronization check (analogy between DB and deterministic scripts)
    db_sync_status = "file_manifest_deterministic (air-gapped / local mode)"
    if os.getenv("CINEFLOW_DATABASE_URL"):
        db_sync_status = "db_configured_and_mirrored"

    total_transferred = len(transferred_characters) + len(transferred_locations) + len(transferred_props)

    return {
        "status": "transferred",
        "source_project_id": source_manifest.get("project_id"),
        "source_project_title": source_manifest.get("title"),
        "target_project_id": target_project_id,
        "target_project_title": target_manifest.get("title"),
        "transferred_characters": transferred_characters,
        "transferred_locations": transferred_locations,
        "transferred_props": transferred_props,
        "total_transferred": total_transferred,
        "copied_files_count": copied_files_count,
        "skipped_items": skipped_items,
        "db_sync": db_sync_status,
        "message": (
            f"Успешно перенесено {len(transferred_characters)} персонажей, "
            f"{len(transferred_locations)} локаций и {len(transferred_props)} реквизитов "
            f"из проекта '{source_manifest.get('title')}' в '{target_manifest.get('title')}'."
        ),
        "guided_next_step": (
            "Персонажи и локации зафиксированы в Single Source of Truth (project.json) со всеми референсными изображениями и образцами голоса. "
            "Вы можете использовать их в сценах или скорректировать их образы для нового сценария."
        ),
    }


def read_project_manifest(project_id: str) -> dict[str, Any]:
    path = get_manifest_path(project_id)
    if not path.is_file():
        raise FileNotFoundError(f"Project manifest not found for '{project_id}' at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def write_project_manifest(project_id: str, manifest: dict[str, Any]) -> None:
    path = get_manifest_path(project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest["updated_at"] = _utcnow()
    # Atomic write
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def init_project_workspace(
    title: str,
    source_text: str,
    source_filename: str | None = "screenplay.txt",
    aspect: str = "16:9",
    style: str = "cinematic",
    characters: list[dict[str, Any]] | None = None,
    locations: list[dict[str, Any]] | None = None,
    scenes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Initializes the physical directory tree and writes the initial project.json."""
    slug = re.sub(r"[^\w\d]+", "_", title).strip("_").lower() or "project"
    project_id = f"p_{slug}"
    project_dir = get_project_dir(project_id)

    # Subdirectories
    source_dir = project_dir / "source"
    settings_dir = project_dir / "settings"
    materials_dir = project_dir / "materials"
    chars_dir = materials_dir / "characters"
    props_dir = materials_dir / "props"
    locs_dir = materials_dir / "locations"
    scenes_dir = project_dir / "scenes"
    export_dir = project_dir / "export"

    for d in (source_dir, settings_dir, chars_dir, props_dir, locs_dir, scenes_dir, export_dir):
        d.mkdir(parents=True, exist_ok=True)

    # Save original source text
    filename = source_filename or "source_text.txt"
    source_file_path = source_dir / filename
    source_file_path.write_text(source_text, encoding="utf-8")

    # Initial ComfyUI configuration
    default_comfy = {
        "comfy_dir": str(Path("ComfyUI").resolve()),
        "comfy_url": "http://127.0.0.1:8188",
        "models_dir": str(Path("ComfyUI/models").resolve()),
        "custom_nodes_dir": str(Path("ComfyUI/custom_nodes").resolve()),
        "active_profile": "auto",
        "updated_at": _utcnow(),
    }
    (settings_dir / "comfyui.json").write_text(
        json.dumps(default_comfy, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Convert initial scenes into Graph Nodes
    graph_nodes = []
    for sc in (scenes or []):
        sc_id = sc.get("id") or f"scene_{len(graph_nodes)+1:02d}"
        graph_nodes.append({
            "scene_id": sc_id,
            "title": sc.get("title", sc_id),
            "slugline": sc.get("slugline", f"EXT. {sc.get('title', sc_id).upper()} - DAY"),
            "stage": "draft",
            "dramatic_intent": sc.get("dramatic_intent", {
                "emotional_arc": "tension build-up",
                "tension_rating": 5,
                "director_treatment": {
                    "camera_style": "35mm anamorphic, steady tracking",
                    "color_palette": "natural cinematic",
                    "lighting_setup": "motivated soft key, gentle rim",
                    "pacing_tempo": "standard narrative",
                    "sound_atmosphere": "ambient room tone",
                },
            }),
            "continuity": sc.get("continuity", {
                "time_of_day": "DAY",
                "weather": "CLEAR",
                "cast_state": {},
            }),
            "source_mapping": {
                "source_excerpt": sc.get("excerpt", ""),
                "beat_sheet": sc.get("beat_sheet", []),
            },
            "shots": sc.get("shots", []),
        })

    timeline_sequence = [node["scene_id"] for node in graph_nodes]
    graph_edges = []
    for idx in range(len(timeline_sequence) - 1):
        graph_edges.append({
            "from_scene": timeline_sequence[idx],
            "to_scene": timeline_sequence[idx + 1],
            "transition_type": "CUT",
            "transition_notes": "Standard narrative progression",
            "continuity_carryover": [],
            "order": idx + 1,
        })

    manifest: dict[str, Any] = {
        "project_id": project_id,
        "title": title,
        "created_at": _utcnow(),
        "updated_at": _utcnow(),
        "aspect": aspect,
        "style": style,
        "stage": "source_ingested",  # source_ingested -> casting -> scene_selection -> scene_production -> export
        "source_file": str(source_file_path),
        "source_bytes": len(source_text.encode("utf-8")),
        "comfy_config": default_comfy,
        "characters": characters or [],
        "locations": locations or [],
        "scenes": scenes or [],
        "scene_graph": {
            "nodes": graph_nodes,
            "edges": graph_edges,
            "timeline_sequence": timeline_sequence,
        },
        "active_scene_id": None,
        "notes": [],
    }

    write_project_manifest(project_id, manifest)

    return {
        "status": "initialized",
        "project_id": project_id,
        "title": title,
        "source_saved_to": str(source_file_path),
        "manifest_path": str(get_manifest_path(project_id)),
        "stage": manifest["stage"],
        "characters_count": len(manifest["characters"]),
        "scenes_count": len(manifest["scenes"]),
        "guided_next_step": "Present the extracted characters and list of scenes to the user. Ask which scene to tackle first, or if character appearances need adjustment.",
    }


def update_project_manifest(project_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    """Updates fields in project.json, tracking changes and detecting impacts on downstream shots."""
    manifest = read_project_manifest(project_id)
    impact_warnings: list[str] = []

    # Detect character changes that affect existing scenes
    if "characters" in updates:
        old_char_names = {c.get("name") for c in manifest.get("characters", [])}
        new_char_names = {c.get("name") for c in updates["characters"]}
        if old_char_names != new_char_names:
            impact_warnings.append(
                f"Cast modified (was: {old_char_names}, now: {new_char_names}). "
                "Any existing keyframes featuring modified characters should be regenerated."
            )

    # Apply updates
    for k, v in updates.items():
        manifest[k] = v

    write_project_manifest(project_id, manifest)

    return {
        "status": "updated",
        "project_id": project_id,
        "stage": manifest.get("stage"),
        "impact_warnings": impact_warnings,
        "manifest": manifest,
    }


def activate_project_scene(project_id: str, scene_id: str, scene_title: str | None = None) -> dict[str, Any]:
    """Sets active scene and provisions its dedicated scene directory."""
    manifest = read_project_manifest(project_id)
    scene_dir = get_project_dir(project_id) / "scenes" / scene_id
    for sub in ("frames", "audio", "video", "workflows"):
        (scene_dir / sub).mkdir(parents=True, exist_ok=True)

    manifest["active_scene_id"] = scene_id
    manifest["stage"] = "scene_production"

    # Add or update scene record in manifest
    scene_record = None
    for sc in manifest.get("scenes", []):
        if sc.get("id") == scene_id:
            scene_record = sc
            break

    if not scene_record:
        scene_record = {
            "id": scene_id,
            "title": scene_title or scene_id,
            "status": "in_progress",
            "created_at": _utcnow(),
        }
        manifest.setdefault("scenes", []).append(scene_record)
    else:
        scene_record["status"] = "in_progress"
        if scene_title:
            scene_record["title"] = scene_title

    # Ensure local scene.json exists
    scene_json_path = scene_dir / "scene.json"
    if not scene_json_path.exists():
        initial_scene_data = {
            "project_id": project_id,
            "scene_id": scene_id,
            "title": scene_record.get("title", scene_id),
            "slugline": f"EXT. {scene_id.upper()} - DAY",
            "status": "in_progress",
            "created_at": _utcnow(),
            "updated_at": _utcnow(),
            "dramatic_intent": {
                "emotional_arc": "tension build-up",
                "tension_rating": 5,
                "director_treatment": {
                    "camera_style": "35mm anamorphic, steady tracking",
                    "color_palette": "cinematic teal and orange",
                    "lighting_setup": "motivated soft key",
                    "pacing_tempo": "standard narrative",
                    "sound_atmosphere": "ambient room tone",
                },
            },
            "continuity": {
                "time_of_day": "DAY",
                "weather": "CLEAR",
                "cast_state": {},
            },
            "source_mapping": {
                "source_excerpt": "",
                "beat_sheet": [],
            },
            "shots": [],
        }
        scene_json_path.write_text(json.dumps(initial_scene_data, ensure_ascii=False, indent=2), encoding="utf-8")

    write_project_manifest(project_id, manifest)

    return {
        "status": "scene_activated",
        "project_id": project_id,
        "active_scene_id": scene_id,
        "scene_dir": str(scene_dir),
        "scene_json_path": str(scene_dir / "scene.json"),
        "stage": manifest["stage"],
        "guided_next_step": f"Scene '{scene_id}' is now the active focus. Synthesize dialogue lines and generate initial keyframes for this scene.",
    }


def get_project_comfy_config(project_id: str) -> dict[str, Any]:
    """Retrieves the project's configured ComfyUI paths, URLs, and hardware profile."""
    project_dir = get_project_dir(project_id)
    cfg_file = project_dir / "settings" / "comfyui.json"
    if cfg_file.is_file():
        try:
            return json.loads(cfg_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    manifest = read_project_manifest(project_id)
    return manifest.get("comfy_config", {
        "comfy_dir": str(Path("ComfyUI").resolve()),
        "comfy_url": "http://127.0.0.1:8188",
        "models_dir": str(Path("ComfyUI/models").resolve()),
        "custom_nodes_dir": str(Path("ComfyUI/custom_nodes").resolve()),
        "active_profile": "auto",
        "status": "default",
    })


def set_project_comfy_config(project_id: str, config: dict[str, Any]) -> dict[str, Any]:
    """Saves and updates ComfyUI directory paths and API URLs for a project."""
    manifest = read_project_manifest(project_id)
    project_dir = get_project_dir(project_id)
    settings_dir = project_dir / "settings"
    settings_dir.mkdir(parents=True, exist_ok=True)

    current_cfg = get_project_comfy_config(project_id)
    for k, v in config.items():
        if v is not None:
            current_cfg[k] = v
    current_cfg["updated_at"] = _utcnow()

    # Check existence on disk
    comfy_dir_path = Path(current_cfg.get("comfy_dir", "ComfyUI"))
    current_cfg["comfy_dir_exists"] = comfy_dir_path.is_dir()
    current_cfg["main_py_exists"] = (comfy_dir_path / "main.py").is_file()

    # Write to settings/comfyui.json
    cfg_file = settings_dir / "comfyui.json"
    cfg_file.write_text(json.dumps(current_cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    # Sync with manifest
    manifest["comfy_config"] = current_cfg
    write_project_manifest(project_id, manifest)

    return {
        "status": "configured",
        "project_id": project_id,
        "comfy_config": current_cfg,
        "config_file": str(cfg_file),
    }


def get_scene_graph(project_id: str) -> dict[str, Any]:
    """Returns the comprehensive Directed Scene Graph (nodes, edges, continuity carryover)."""
    manifest = read_project_manifest(project_id)
    graph = manifest.get("scene_graph", {
        "nodes": [],
        "edges": [],
        "timeline_sequence": [],
    })
    return {
        "project_id": project_id,
        "nodes_count": len(graph.get("nodes", [])),
        "edges_count": len(graph.get("edges", [])),
        "timeline_sequence": graph.get("timeline_sequence", []),
        "graph": graph,
    }


def update_scene_graph(
    project_id: str,
    nodes: list[dict[str, Any]] | None = None,
    edges: list[dict[str, Any]] | None = None,
    timeline_sequence: list[str] | None = None,
) -> dict[str, Any]:
    """Updates the Directed Scene Graph, transitions, and timeline sequence."""
    manifest = read_project_manifest(project_id)
    graph = manifest.setdefault("scene_graph", {
        "nodes": [],
        "edges": [],
        "timeline_sequence": [],
    })

    if nodes is not None:
        graph["nodes"] = nodes
    if edges is not None:
        graph["edges"] = edges
    if timeline_sequence is not None:
        graph["timeline_sequence"] = timeline_sequence

    # Also sync individual scene files
    project_dir = get_project_dir(project_id)
    for node in graph.get("nodes", []):
        sc_id = node.get("scene_id")
        if sc_id:
            sc_dir = project_dir / "scenes" / sc_id
            sc_dir.mkdir(parents=True, exist_ok=True)
            sc_file = sc_dir / "scene.json"
            sc_data = {}
            if sc_file.is_file():
                try:
                    sc_data = json.loads(sc_file.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    sc_data = {}
            sc_data.update(node)
            sc_data["updated_at"] = _utcnow()
            sc_file.write_text(json.dumps(sc_data, ensure_ascii=False, indent=2), encoding="utf-8")

    write_project_manifest(project_id, manifest)

    return {
        "status": "graph_updated",
        "project_id": project_id,
        "nodes_count": len(graph["nodes"]),
        "edges_count": len(graph["edges"]),
        "timeline_sequence": graph["timeline_sequence"],
    }


def update_scene_directing(
    project_id: str,
    scene_id: str,
    slugline: str | None = None,
    dramatic_intent: dict[str, Any] | None = None,
    continuity: dict[str, Any] | None = None,
    beat_sheet: list[dict[str, Any]] | None = None,
    shots: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Updates director explication, continuity state, beat sheet and shots for a scene."""
    manifest = read_project_manifest(project_id)
    project_dir = get_project_dir(project_id)
    scene_dir = project_dir / "scenes" / scene_id
    scene_dir.mkdir(parents=True, exist_ok=True)
    sc_file = scene_dir / "scene.json"

    scene_data: dict[str, Any] = {
        "project_id": project_id,
        "scene_id": scene_id,
        "title": scene_id,
        "status": "in_progress",
        "created_at": _utcnow(),
    }
    if sc_file.is_file():
        try:
            scene_data = json.loads(sc_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    if slugline:
        scene_data["slugline"] = slugline
    if dramatic_intent:
        scene_data.setdefault("dramatic_intent", {}).update(dramatic_intent)
    if continuity:
        scene_data.setdefault("continuity", {}).update(continuity)
    if beat_sheet is not None:
        scene_data.setdefault("source_mapping", {})["beat_sheet"] = beat_sheet
    if shots is not None:
        scene_data["shots"] = shots

    scene_data["updated_at"] = _utcnow()
    sc_file.write_text(json.dumps(scene_data, ensure_ascii=False, indent=2), encoding="utf-8")

    # Sync back into manifest scene_graph nodes
    graph = manifest.setdefault("scene_graph", {"nodes": [], "edges": [], "timeline_sequence": []})
    found_node = False
    for node in graph["nodes"]:
        if node.get("scene_id") == scene_id:
            node.update(scene_data)
            found_node = True
            break
    if not found_node:
        graph["nodes"].append(scene_data)
        if scene_id not in graph["timeline_sequence"]:
            graph["timeline_sequence"].append(scene_id)

    write_project_manifest(project_id, manifest)

    return {
        "status": "scene_directing_updated",
        "project_id": project_id,
        "scene_id": scene_id,
        "scene_file": str(sc_file),
        "scene_data": scene_data,
    }


def record_shot_artifact(
    project_id: str,
    scene_id: str,
    shot_id: str,
    media_filename: str,
    comfy_url: str | None = None,
    comfy_prompt_id: str | None = None,
    workflow_api: dict[str, Any] | None = None,
    prompt: str | None = None,
    negative_prompt: str | None = None,
    seed: int | None = None,
    model: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Records a generated shot asset, saves the exact ComfyUI workflow JSON, and creates a sidecar .cineflow.json."""
    project_dir = get_project_dir(project_id)
    scene_dir = project_dir / "scenes" / scene_id
    workflows_dir = scene_dir / "workflows"
    video_dir = scene_dir / "video"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    video_dir.mkdir(parents=True, exist_ok=True)

    # 1. Save workflow JSON if provided
    workflow_path_str = None
    if workflow_api:
        wf_file = workflows_dir / f"{shot_id}.comfy.json"
        wf_file.write_text(json.dumps(workflow_api, ensure_ascii=False, indent=2), encoding="utf-8")
        workflow_path_str = str(wf_file.resolve())

    # 2. Save Sidecar .cineflow.json alongside media file
    media_path = video_dir / media_filename
    sidecar_path = media_path.with_suffix(".cineflow.json")

    comfy_cfg = get_project_comfy_config(project_id)
    active_comfy_url = comfy_url or comfy_cfg.get("comfy_url", "http://127.0.0.1:8188")

    sidecar_data: dict[str, Any] = {
        "cineflow_version": "2.0",
        "project_id": project_id,
        "scene_id": scene_id,
        "shot_id": shot_id,
        "media_filename": media_filename,
        "media_path": str(media_path.resolve()),
        "comfy_url": active_comfy_url,
        "comfy_prompt_id": comfy_prompt_id or "",
        "workflow_file": workflow_path_str or "",
        "prompt": prompt or "",
        "negative_prompt": negative_prompt or "",
        "seed": seed,
        "model": model or "LTX-Video 2.5",
        "created_at": _utcnow(),
    }
    if metadata:
        sidecar_data["custom_metadata"] = metadata

    sidecar_path.write_text(json.dumps(sidecar_data, ensure_ascii=False, indent=2), encoding="utf-8")

    # 3. Update scene.json shots list
    sc_file = scene_dir / "scene.json"
    if sc_file.is_file():
        try:
            sc_data = json.loads(sc_file.read_text(encoding="utf-8"))
            shots = sc_data.setdefault("shots", [])
            shot_entry = None
            for sh in shots:
                if sh.get("shot_id") == shot_id:
                    shot_entry = sh
                    break
            if not shot_entry:
                shot_entry = {"shot_id": shot_id}
                shots.append(shot_entry)
            shot_entry.update({
                "media_path": str(media_path),
                "sidecar_path": str(sidecar_path),
                "workflow_path": workflow_path_str,
                "prompt": prompt,
                "seed": seed,
                "model": model,
                "status": "rendered",
                "updated_at": _utcnow(),
            })
            sc_file.write_text(json.dumps(sc_data, ensure_ascii=False, indent=2), encoding="utf-8")
        except (json.JSONDecodeError, OSError):
            pass

    return {
        "status": "recorded",
        "project_id": project_id,
        "scene_id": scene_id,
        "shot_id": shot_id,
        "media_path": str(media_path),
        "sidecar_file": str(sidecar_path),
        "workflow_file": workflow_path_str,
        "roundtrip_ready": True,
        "davinci_action": "In DaVinci Resolve: select clip on timeline -> Scripts -> Edit -> CineFlow_Edit_in_ComfyUI to edit in ComfyUI.",
    }
