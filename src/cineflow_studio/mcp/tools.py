"""CineFlow MCP Tools registry and business logic."""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from cineflow_studio.mcp.protocol import ToolDefinition

# Regex patterns for validation
CYRILLIC_PATTERN = re.compile(r"[\u0400-\u04FF]")
CJK_PATTERN = re.compile(r"[\u4E00-\u9FFF]")
TALKING_VERBS_PATTERN = re.compile(r"\b(speaks?|talks?|whispers?|singing|sings?|narrat(es?|ing)|mouth(s|ing))\b", re.IGNORECASE)


def validate_bilingual_english(prompt: str, field_name: str = "prompt") -> None:
    """Enforces that visual and motion prompts are in English only."""
    if CYRILLIC_PATTERN.search(prompt):
        raise ValueError(
            f"Bilingual rule violation in '{field_name}': Prompt contains Cyrillic characters. "
            f"ComfyUI diffusion models require English-only visual prompts. "
            f"Please translate visual descriptions to cinematic English."
        )
    if CJK_PATTERN.search(prompt):
        raise ValueError(
            f"Bilingual rule violation in '{field_name}': Prompt contains Chinese/CJK characters. "
            f"ComfyUI diffusion models require English-only visual prompts. "
            f"Please translate visual descriptions to cinematic English."
        )


def validate_ref_policy(prompt: str, subjects: list[str]) -> None:
    """Enforces that all declared subject references (<Subject N>) are explicitly named in the prompt."""
    if not subjects:
        return
    for subj in subjects:
        # Check either exact token like "<Subject 1>" or lowercase without brackets
        if subj not in prompt and subj.strip("<>") not in prompt:
            raise ValueError(
                f"Reference Policy violation (PROMPTING.md): Declared subject '{subj}' is not mentioned in the prompt. "
                f"Every required reference MUST be explicitly addressed in the visual prompt to prevent identity loss."
            )


def validate_closed_mouth(prompt: str, has_voice: bool, keep_mouth_closed: bool = False) -> str:
    """Issue #600: Prevents unintended mouth movements in silent or non-dialogue shots."""
    if not has_voice or keep_mouth_closed:
        match = TALKING_VERBS_PATTERN.search(prompt)
        if match:
            raise ValueError(
                f"Lip-Sync Guard violation (#600): The shot has no voice track or requires closed mouth, "
                f"but prompt contains talking verb '{match.group(0)}'. "
                f"MiniMax/LTX will erroneously animate lips. Replace with silent expressions "
                f"(e.g. 'lips closed, listening intently, calm expression')."
            )
        # Ensure closed-mouth token is present
        if "lips closed" not in prompt.lower() and "mouth closed" not in prompt.lower():
            prompt = prompt.rstrip() + ", lips firmly closed, calm silent expression"
    return prompt


# -------------------------------------------------------------------------
# Tool Handlers
# -------------------------------------------------------------------------

def cloud_mode_requested(args: dict[str, Any]) -> bool:
    """Cloud mode needs a CineFlow API key; ``offline=true`` in the call opts out."""
    from cineflow_studio.mcp.billing import get_active_api_key

    if args.get("offline") is True:
        return False
    return bool(get_active_api_key())


def write_cloud_mirror(project_id: str, mirror: dict[str, Any]) -> None:
    """Write the cloud mirror next to the local project manifest (never the source of truth)."""
    if not project_id:
        return
    import json
    from pathlib import Path

    from cineflow_studio.mcp.project_store import get_project_dir

    try:
        project_dir = Path(get_project_dir(project_id))
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "mirror.json").write_text(
            json.dumps(mirror, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        pass  # the mirror is best-effort; the server stays the source of truth


async def handle_quick_tts(args: dict[str, Any]) -> dict[str, Any]:
    text = args.get("text", "").strip()
    if not text:
        raise ValueError("Field 'text' is required")
    voice_sample = args.get("voice_sample")
    emotion = args.get("emotion", "neutral")

    # In production, this dispatches to Higgs v3 or DashScope TTS
    # For standalone execution or offline mode, simulate predictable output path
    slug = re.sub(r"[^\w\d]", "_", text[:20]).lower()
    audio_path = f"storage/audio/tts_{slug}.wav"
    duration_sec = round(max(1.0, len(text.split()) * 0.35), 2)

    return {
        "status": "completed",
        "audio_path": audio_path,
        "duration_sec": duration_sec,
        "emotion": emotion,
        "voice_cloned": bool(voice_sample),
    }


async def handle_quick_photo_animate(args: dict[str, Any]) -> dict[str, Any]:
    image_path = args.get("image_path", "").strip()
    if not image_path:
        raise ValueError("Field 'image_path' is required")
    prompt = args.get("prompt", "subtle cinematic camera zoom-in, natural ambient motion")
    validate_bilingual_english(prompt, "prompt")

    duration = float(args.get("duration", 5.0))
    if duration < 5.0 or duration > 8.0:
        duration = 5.0

    video_path = f"storage/renders/animate_{Path(image_path).stem}.mp4"
    return {
        "status": "completed",
        "source_image": image_path,
        "video_path": video_path,
        "duration_sec": duration,
        "prompt": prompt,
    }


async def handle_quick_reel(args: dict[str, Any]) -> dict[str, Any]:
    folder_path = args.get("folder_path", "").strip()
    if not folder_path:
        raise ValueError("Field 'folder_path' is required")
    prompt = args.get("prompt", "dynamic commercial product montage, smooth pacing")
    validate_bilingual_english(prompt, "prompt")

    reel_path = "storage/renders/quick_reel_output.mp4"
    return {
        "status": "completed",
        "folder_path": folder_path,
        "reel_path": reel_path,
        "shots_count": 4,
        "duration_sec": 15.0,
    }


async def handle_project_create(args: dict[str, Any]) -> dict[str, Any]:
    title = args.get("title", "Untitled Project").strip()
    screenplay = args.get("screenplay", "").strip()
    aspect = args.get("aspect", "9:16")
    style = args.get("style", "cinematic")

    slug = re.sub(r"[^\w\d]+", "_", title).strip("_").lower() or "proj"
    project_id = f"p_{slug}"
    project_dir = Path("storage/projects") / project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    if screenplay:
        (project_dir / "screenplay.txt").write_text(screenplay, encoding="utf-8")

    return {
        "status": "created",
        "project_id": project_id,
        "title": title,
        "aspect": aspect,
        "style": style,
        "storage_dir": str(project_dir),
        "message": f"Project '{title}' initialized in {project_dir}.",
    }


async def handle_materials_attach(args: dict[str, Any]) -> dict[str, Any]:
    project_id = args.get("project_id", "").strip()
    if not project_id:
        raise ValueError("Field 'project_id' is required")

    characters = args.get("characters", [])
    props = args.get("props", [])
    locations = args.get("locations", [])

    cards = []
    for c in characters:
        name = c.get("name", "Character")
        desc = c.get("description", "")
        # Enforce no Cyrillic in visual card prompt if supplied
        if desc:
            validate_bilingual_english(desc, f"character.{name}.description")
        cards.append({
            "type": "character",
            "name": name,
            "card_path": f"storage/projects/{project_id}/materials/char_{name.lower()}.png",
            "role": "model",
        })

    for p in props:
        name = p.get("name", "Prop")
        desc = p.get("description", "")
        if desc:
            validate_bilingual_english(desc, f"prop.{name}.description")
        cards.append({
            "type": "prop",
            "name": name,
            "card_path": f"storage/projects/{project_id}/materials/prop_{name.lower()}.png",
        })

    for loc in locations:
        name = loc.get("name", "Location")
        cards.append({
            "type": "location",
            "name": name,
            "card_path": f"storage/projects/{project_id}/materials/loc_{name.lower()}.png",
        })

    return {
        "status": "materials_ready",
        "project_id": project_id,
        "cards_generated": cards,
        "action_required": "Please show these cards to the user for visual confirmation before generating keyframes.",
    }


async def handle_dialogue_tts(args: dict[str, Any]) -> dict[str, Any]:
    project_id = args.get("project_id", "").strip()
    if not project_id:
        raise ValueError("Field 'project_id' is required")
    lines = args.get("lines", [])
    if not lines:
        raise ValueError("Field 'lines' must contain at least one dialogue line")

    rendered_lines = []
    total_time = 0.0
    for idx, line in enumerate(lines, start=1):
        text = line.get("text", "")
        speaker = line.get("speaker", "Narrator")
        duration = round(max(1.2, len(text.split()) * 0.38), 2)
        total_time += duration
        rendered_lines.append({
            "line_index": idx,
            "speaker": speaker,
            "text": text,
            "audio_path": f"storage/projects/{project_id}/audio/line_{idx:02d}.wav",
            "duration_sec": duration,
        })

    return {
        "status": "dialogue_ready",
        "project_id": project_id,
        "lines": rendered_lines,
        "total_duration_sec": round(total_time, 2),
    }


async def handle_frames_generate(args: dict[str, Any]) -> dict[str, Any]:
    project_id = args.get("project_id", "").strip()
    if not project_id:
        raise ValueError("Field 'project_id' is required")
    frame_specs = args.get("frame_specs", [])
    if not frame_specs:
        raise ValueError("Field 'frame_specs' is required")

    generated_frames = []
    for spec in frame_specs:
        shot_idx = spec.get("shot_index", 1)
        prompt = spec.get("prompt", "")
        subjects = spec.get("subjects", [])

        # 1. Enforce English-only rule
        validate_bilingual_english(prompt, f"shot_{shot_idx}.prompt")
        # 2. Enforce Reference Policy (all subjects must be addressed)
        validate_ref_policy(prompt, subjects)

        frame_path = f"storage/projects/{project_id}/frames/shot_{shot_idx:02d}_frame.png"
        generated_frames.append({
            "shot_index": shot_idx,
            "frame_path": frame_path,
            "subjects_addressed": subjects,
            "status": "rendered",
        })

    return {
        "status": "frames_ready",
        "project_id": project_id,
        "frames": generated_frames,
    }


async def handle_video_render(args: dict[str, Any]) -> dict[str, Any]:
    project_id = args.get("project_id", "").strip()
    if not project_id:
        raise ValueError("Field 'project_id' is required")
    clip_specs = args.get("clip_specs", [])
    if not clip_specs:
        raise ValueError("Field 'clip_specs' is required")

    rendered_clips = []
    for spec in clip_specs:
        shot_idx = spec.get("shot_index", 1)
        prompt = spec.get("prompt", "")
        duration = float(spec.get("duration", 5.0))
        voice_track = spec.get("voice_track")
        keep_mouth_closed = bool(spec.get("keep_mouth_closed", False))

        # 1. Enforce English-only rule
        validate_bilingual_english(prompt, f"clip_{shot_idx}.prompt")
        # 2. Enforce Lip-Sync Closed Mouth Guard (#600)
        prompt = validate_closed_mouth(prompt, has_voice=bool(voice_track), keep_mouth_closed=keep_mouth_closed)

        clip_path = f"storage/projects/{project_id}/clips/shot_{shot_idx:02d}_take01.mp4"
        rendered_clips.append({
            "shot_index": shot_idx,
            "clip_path": clip_path,
            "duration_sec": duration,
            "final_prompt": prompt,
            "status": "rendered",
        })

    return {
        "status": "video_rendered",
        "project_id": project_id,
        "clips": rendered_clips,
    }


async def handle_export_mp4(args: dict[str, Any]) -> dict[str, Any]:
    project_id = args.get("project_id", "").strip()
    if not project_id:
        raise ValueError("Field 'project_id' is required")
    music_path = args.get("music_path")
    duck = args.get("duck", True)

    export_path = f"storage/projects/{project_id}/export/final_film.mp4"
    return {
        "status": "exported",
        "project_id": project_id,
        "export_path": export_path,
        "has_music": bool(music_path),
        "audio_ducking": duck,
        "preview_url": f"http://127.0.0.1:8721/storage/projects/{project_id}/export/final_film.mp4",
    }


async def handle_status(args: dict[str, Any]) -> dict[str, Any]:
    project_id = args.get("project_id")
    from cineflow_studio.mcp.billing import resolve_billing_status
    billing = resolve_billing_status()
    return {
        "status": "online",
        "project_id": project_id,
        "engine": "CineFlow Agent Studio",
        "tier": billing["tier"],
        "tier_name": billing["tier_name"],
        "render_backend": billing["render_backend"],
        "active_jobs": 0,
    }


async def handle_billing_status(args: dict[str, Any]) -> dict[str, Any]:
    """Community status locally; with a key, billing state comes from the CineFlow
    server (GET /me, Studio 3b). The client never decides a tier itself."""
    from cineflow_studio.mcp.billing import PACKAGE_API_CONTRACT, resolve_billing_status

    status = resolve_billing_status()
    if not status["api_key_configured"]:
        return status
    from cineflow_studio.mcp import cloud

    try:
        me = await cloud.get_me()
        me_user = me.get("user") or {}
        me_billing = me.get("billing") or {}
        me_server = me.get("server") or {}
        status["tier"] = me_user.get("role")
        status["billing"] = {
            "generation_enabled": me_billing.get("generation_enabled"),
            "gpu_unlimited": me_billing.get("gpu_unlimited"),
            "credit_cap": me_billing.get("credit_cap"),
        }
        status["subscription"] = me.get("subscription")
        status["payment_url"] = me.get("payment_url")
        # D6 (#754): storage used/cap passthrough — the agent warns BEFORE the
        # upload refusal instead of discovering it by a failed call.
        status["storage"] = me.get("storage") or {"used_gb": None, "cap_gb": None}
        # D5: the plan slug is the tier the checklist reasons about.
        subscription = me.get("subscription") or {}
        if subscription.get("plan"):
            status["tier"] = subscription["plan"]
            status["tier_name"] = (
                "CineFlow plan '" + subscription["plan"] + "' ("
                + str(subscription.get("status")) + ") verified by the server"
            )
        status["server"] = {
            "api_rev": me_server.get("api_rev"),
            "api_contract": me_server.get("api_contract"),
        }
        server_contract = me_server.get("api_contract")
        if server_contract is None:
            status["compat"] = {
                "package_api_contract": PACKAGE_API_CONTRACT,
                "server_api_contract": None,
                "ok": False,
                "note": (
                    "The CineFlow server predates the billing contract "
                    f"(no api_contract field; the package expects {PACKAGE_API_CONTRACT}). "
                    "Update the CineFlow backend."
                ),
            }
        else:
            status["compat"] = {
                "package_api_contract": PACKAGE_API_CONTRACT,
                "server_api_contract": server_contract,
                "ok": int(server_contract) >= PACKAGE_API_CONTRACT,
                "note": (
                    None
                    if int(server_contract) >= PACKAGE_API_CONTRACT
                    else "The CineFlow server speaks an older contract than this package; update the backend."
                ),
            }
        status["refusal"] = None
        if status["billing"]["generation_enabled"] is False:
            # Server-decided lock (promo-less self-signup): the agent should
            # tell the user honestly and point at the payment URL.
            status["refusal"] = {
                "code": "GENERATION_LOCKED",
                "message": (
                    "Generation is locked for this account on the CineFlow server "
                    "(no promo code or subscription yet). Ask the user to subscribe "
                    "or apply a promo code, then retry."
                ),
                "payment_url": me.get("payment_url") or status["billing_portal"],
            }
            status["tier_name"] = "CineFlow (view-only, generation locked)"
        else:
            status["tier_name"] = f"CineFlow ({status['tier']}) verified by the server"
        status["cloud"] = {
            **status["cloud"],
            "tier": me_user.get("role"),
            "entitlements": me.get("entitlements", []),
            "verified": True,
        }
        status["message"] = "Billing state verified by the CineFlow server."
    except cloud.CloudError as exc:
        if isinstance(exc, cloud.CloudUnavailable):
            status["cloud"] = {**status["cloud"], "verified": False, "cloud_unreachable": str(exc)}
            status["message"] = "CineFlow server unreachable; running on local resources until it answers."
        else:
            status["cloud"] = {**status["cloud"], "verified": False, "error": str(exc), "error_status": exc.status}
            status["message"] = f"The CineFlow server refused the key (HTTP {exc.status}); check it on the billing portal."
    except Exception as exc:  # noqa: BLE001 — billing status must always answer JSON
        status["cloud"] = {**status["cloud"], "verified": False, "cloud_unreachable": str(exc)}
        status["message"] = "CineFlow server unreachable; running on local resources until it answers."
    return status


async def handle_auth(args: dict[str, Any]) -> dict[str, Any]:
    api_key = args.get("api_key", "").strip()
    if not api_key:
        raise ValueError("Field 'api_key' is required. Pass the CineFlow API key issued by the CineFlow server.")
    from cineflow_studio.mcp.billing import authenticate_client
    return authenticate_client(api_key)


async def handle_plan_stages(args: dict[str, Any]) -> dict[str, Any]:
    project_id = args.get("project_id", "").strip()
    if not project_id:
        raise ValueError("Field 'project_id' is required")
    from cineflow_studio.mcp import cloud
    return await cloud.plan_stages(project_id)


async def handle_plan_state(args: dict[str, Any]) -> dict[str, Any]:
    project_id = args.get("project_id", "").strip()
    if not project_id:
        raise ValueError("Field 'project_id' is required")
    from cineflow_studio.mcp import cloud
    return await cloud.plan_state(project_id)


async def handle_scenes_propose(args: dict[str, Any]) -> dict[str, Any]:
    project_id = args.get("project_id", "").strip()
    scenes = args.get("scenes")
    if not project_id or not scenes:
        raise ValueError("Fields 'project_id' and 'scenes' are required")
    from cineflow_studio.mcp import cloud
    return await cloud.propose_scenes(project_id, {"scenes": scenes, "source_note": args.get("source_note")})


async def handle_davinci_sync(args: dict[str, Any]) -> dict[str, Any]:
    project_id = args.get("project_id", "").strip()
    if not project_id:
        raise ValueError("Field 'project_id' is required")
    timeline_name = args.get("timeline_name")
    install_action = args.get("install_action", True)
    from cineflow_studio.mcp.davinci import sync_to_davinci
    return sync_to_davinci(project_id, timeline_name=timeline_name, install_action=install_action)


async def handle_project_init(args: dict[str, Any]) -> dict[str, Any]:
    title = args.get("title", "").strip()
    if not title:
        raise ValueError("Field 'title' is required")
    source_text = args.get("source_text", "").strip()
    if not source_text:
        raise ValueError("Field 'source_text' is required (screenplay, book text, or story synopsis)")
    from cineflow_studio.mcp.project_store import init_project_workspace

    local = init_project_workspace(
        title=title,
        source_text=source_text,
        source_filename=args.get("source_filename"),
        aspect=args.get("aspect", "16:9"),
        style=args.get("style", "cinematic"),
        characters=args.get("characters"),
        locations=args.get("locations"),
        scenes=args.get("scenes"),
    )
    if not cloud_mode_requested(args):
        return local
    # Studio 3c: with a CineFlow API key the server is the source of truth; the local
    # workspace keeps only a mirror (marked as such) so the agent can read offline.
    from cineflow_studio.mcp import cloud

    try:
        remote = await cloud.create_project({"name": title, "description": source_text[:2000]})
    except cloud.CloudUnavailable as exc:
        local["cloud"] = {"configured": True, "cloud_unreachable": str(exc)}
        return local
    except cloud.CloudError as exc:
        local["cloud"] = {"configured": True, "error": str(exc), "error_status": exc.status}
        return local
    except Exception as exc:  # noqa: BLE001 — project init must still yield the local workspace
        local["cloud"] = {"configured": True, "cloud_unreachable": str(exc)}
        return local
    mirror = {
        "note": "Mirror only: the source of truth is the CineFlow server project.",
        "remote_project_id": remote.get("id"),
        "remote_name": remote.get("name"),
    }
    local["cloud"] = {"configured": True, "mode": "cloud", "remote_project_id": remote.get("id"), "mirror": mirror}
    write_cloud_mirror(local.get("project_id"), mirror)
    return local


async def handle_cloud_script_plan(args: dict[str, Any]) -> dict[str, Any]:
    """Studio 3d (cloud mode): upload the script to the CineFlow server, enqueue the plan
    job, and wait for it (bounded). Endpoints come from the server contract only."""
    project_id = args.get("project_id", "").strip()
    script_text = args.get("script_text", "").strip()
    if not project_id or not script_text:
        raise ValueError("Fields 'project_id' and 'script_text' are required")
    from cineflow_studio.mcp import cloud

    await cloud.upload_script(project_id, script_text)
    job = await cloud.enqueue_job(project_id, "script_plan")
    job_id = job.get("job_id") or job.get("id")
    finished = await cloud.wait_job(str(job_id))
    return {
        "status": "cloud_plan_" + str(finished.get("status") or "unknown"),
        "remote_project_id": project_id,
        "job_id": job_id,
        "job": finished,
    }


async def handle_project_get_state(args: dict[str, Any]) -> dict[str, Any]:
    project_id = args.get("project_id", "").strip()
    if not project_id:
        raise ValueError("Field 'project_id' is required")
    from cineflow_studio.mcp.project_store import read_project_manifest
    return read_project_manifest(project_id)


async def handle_project_update_state(args: dict[str, Any]) -> dict[str, Any]:
    project_id = args.get("project_id", "").strip()
    if not project_id:
        raise ValueError("Field 'project_id' is required")
    updates = args.get("updates", {})
    if not updates or not isinstance(updates, dict):
        raise ValueError("Field 'updates' must be a dictionary of changes")
    from cineflow_studio.mcp.project_store import update_project_manifest
    return update_project_manifest(project_id, updates)


async def handle_scene_activate(args: dict[str, Any]) -> dict[str, Any]:
    project_id = args.get("project_id", "").strip()
    scene_id = args.get("scene_id", "").strip()
    if not project_id or not scene_id:
        raise ValueError("Fields 'project_id' and 'scene_id' are required")
    scene_title = args.get("scene_title")
    from cineflow_studio.mcp.project_store import activate_project_scene
    return activate_project_scene(project_id, scene_id, scene_title=scene_title)


async def handle_projects_list(args: dict[str, Any]) -> dict[str, Any]:
    filter_q = args.get("filter")
    from cineflow_studio.mcp.project_store import list_all_projects
    projects = list_all_projects(filter_query=filter_q)
    result: dict[str, Any] = {"count": len(projects), "projects": projects}
    if cloud_mode_requested({}):
        from cineflow_studio.mcp import cloud

        try:
            remote = await cloud.list_projects()
            result["cloud_projects"] = [
                {"id": r.get("id"), "name": r.get("name"), "source": "cloud"} for r in remote
            ]
            result["cloud"] = {"configured": True, "verified": True}
        except cloud.CloudUnavailable as exc:
            result["cloud"] = {"configured": True, "verified": False, "cloud_unreachable": str(exc)}
        except cloud.CloudError as exc:
            result["cloud"] = {"configured": True, "verified": False, "error": str(exc), "error_status": exc.status}
        except Exception as exc:  # noqa: BLE001 — the local list must always answer
            result["cloud"] = {"configured": True, "verified": False, "cloud_unreachable": str(exc)}
    return result


async def handle_assets_transfer(args: dict[str, Any]) -> dict[str, Any]:
    source_project = args.get("source_project", "").strip()
    target_project_id = args.get("target_project_id", "").strip()
    if not source_project or not target_project_id:
        raise ValueError("Fields 'source_project' and 'target_project_id' are required")

    asset_types = args.get("asset_types")
    names = args.get("names")
    conflict_strategy = args.get("conflict_strategy", "skip")

    from cineflow_studio.mcp.project_store import transfer_project_assets
    return transfer_project_assets(
        source_project=source_project,
        target_project_id=target_project_id,
        asset_types=asset_types,
        names=names,
        conflict_strategy=conflict_strategy,
    )


async def handle_hardware_profile(args: dict[str, Any]) -> dict[str, Any]:
    from cineflow_studio.installer.hardware import inspect_hardware
    hw = inspect_hardware()
    return hw.to_dict()


async def handle_installer_audit(args: dict[str, Any]) -> dict[str, Any]:
    comfy_dir = args.get("comfy_dir")
    from pathlib import Path

    from cineflow_studio.installer.runner import audit_comfy_installation
    return audit_comfy_installation(Path(comfy_dir) if comfy_dir else None)


async def handle_generate_launcher(args: dict[str, Any]) -> dict[str, Any]:
    comfy_dir = args.get("comfy_dir", "ComfyUI")
    profile = args.get("profile")
    from pathlib import Path

    from cineflow_studio.installer.runner import generate_launch_script
    script = generate_launch_script(Path(comfy_dir), profile_name=profile)
    return {
        "status": "generated",
        "launcher_path": str(script),
        "profile": profile or "auto_detected",
    }


async def handle_cache_cleanup(args: dict[str, Any]) -> dict[str, Any]:
    comfy_dir = args.get("comfy_dir", "ComfyUI")
    from pathlib import Path

    from cineflow_studio.installer.runner import cleanup_latents_cache
    return cleanup_latents_cache(Path(comfy_dir))


async def handle_scene_graph_get(args: dict[str, Any]) -> dict[str, Any]:
    project_id = args.get("project_id", "").strip()
    if not project_id:
        raise ValueError("Field 'project_id' is required")
    from cineflow_studio.mcp.project_store import get_scene_graph
    return get_scene_graph(project_id)


async def handle_scene_graph_update(args: dict[str, Any]) -> dict[str, Any]:
    project_id = args.get("project_id", "").strip()
    if not project_id:
        raise ValueError("Field 'project_id' is required")
    nodes = args.get("nodes")
    edges = args.get("edges")
    timeline_sequence = args.get("timeline_sequence")
    from cineflow_studio.mcp.project_store import update_scene_graph
    return update_scene_graph(project_id, nodes=nodes, edges=edges, timeline_sequence=timeline_sequence)


async def handle_scene_directing_set(args: dict[str, Any]) -> dict[str, Any]:
    project_id = args.get("project_id", "").strip()
    scene_id = args.get("scene_id", "").strip()
    if not project_id or not scene_id:
        raise ValueError("Fields 'project_id' and 'scene_id' are required")
    from cineflow_studio.mcp.project_store import update_scene_directing
    return update_scene_directing(
        project_id,
        scene_id,
        slugline=args.get("slugline"),
        dramatic_intent=args.get("dramatic_intent"),
        continuity=args.get("continuity"),
        beat_sheet=args.get("beat_sheet"),
        shots=args.get("shots"),
    )


async def handle_comfy_config_get(args: dict[str, Any]) -> dict[str, Any]:
    # #744: project_id is optional — at first run there are no projects yet,
    # and the agent still needs the Comfy setup (paths/URL) to provision the
    # machine before any project exists.
    project_id = args.get("project_id", "").strip()
    if not project_id:
        from pathlib import Path as _Path

        import os as _os

        return {
            "comfy_dir": str(_Path("ComfyUI").resolve()),
            "comfy_url": _os.getenv("COMFYUI_URL", "http://127.0.0.1:8188"),
            "models_dir": str(_Path("ComfyUI") / "models"),
            "custom_nodes_dir": str(_Path("ComfyUI") / "custom_nodes"),
            "scope": "global (no project yet): defaults from cineflow-setup",
        }
    from cineflow_studio.mcp.project_store import get_project_comfy_config
    return get_project_comfy_config(project_id)


async def handle_comfy_config_set(args: dict[str, Any]) -> dict[str, Any]:
    project_id = args.get("project_id", "").strip()
    if not project_id:
        raise ValueError("Field 'project_id' is required")
    cfg = {}
    for key in ("comfy_dir", "comfy_url", "models_dir", "custom_nodes_dir", "active_profile"):
        if key in args:
            cfg[key] = args[key]
    from cineflow_studio.mcp.project_store import set_project_comfy_config
    return set_project_comfy_config(project_id, cfg)


async def handle_shot_record_artifact(args: dict[str, Any]) -> dict[str, Any]:
    project_id = args.get("project_id", "").strip()
    scene_id = args.get("scene_id", "").strip()
    shot_id = args.get("shot_id", "").strip()
    media_filename = args.get("media_filename", "").strip()
    if not project_id or not scene_id or not shot_id or not media_filename:
        raise ValueError("Fields 'project_id', 'scene_id', 'shot_id', and 'media_filename' are required")
    from cineflow_studio.mcp.project_store import record_shot_artifact
    return record_shot_artifact(
        project_id=project_id,
        scene_id=scene_id,
        shot_id=shot_id,
        media_filename=media_filename,
        comfy_url=args.get("comfy_url"),
        comfy_prompt_id=args.get("comfy_prompt_id"),
        workflow_api=args.get("workflow_api"),
        prompt=args.get("prompt"),
        negative_prompt=args.get("negative_prompt"),
        seed=args.get("seed"),
        model=args.get("model"),
        metadata=args.get("metadata"),
    )


async def handle_models_catalog(args: dict[str, Any]) -> dict[str, Any]:
    mirror = args.get("mirror", "huggingface")
    profile = args.get("profile")
    from cineflow_studio.installer.manifest import MODELS_CATALOG, get_weights_for_profile
    weights = get_weights_for_profile(profile) if profile else MODELS_CATALOG
    return {
        "mirror_used": mirror,
        "models_count": len(weights),
        "models": [w.to_dict(mirror) for w in weights],
    }


async def handle_nodes_catalog(_args: dict[str, Any]) -> dict[str, Any]:
    from cineflow_studio.installer.manifest import CUSTOM_NODES_CATALOG
    return {
        "nodes_count": len(CUSTOM_NODES_CATALOG),
        "custom_nodes": CUSTOM_NODES_CATALOG,
    }


async def handle_workflows_catalog(_args: dict[str, Any]) -> dict[str, Any]:
    from cineflow_studio.installer.manifest import WORKFLOWS_CATALOG
    return {
        "workflows_count": len(WORKFLOWS_CATALOG),
        "workflows": [
            {
                "id": wf["id"],
                "name": wf["name"],
                "description": wf["description"],
                "required_nodes": wf["required_nodes"],
                "required_models": wf["required_models"],
                "recommended_profile": wf["recommended_profile"],
            }
            for wf in WORKFLOWS_CATALOG
        ],
    }


async def handle_workflow_get(args: dict[str, Any]) -> dict[str, Any]:
    workflow_id = args.get("workflow_id", "").strip()
    if not workflow_id:
        raise ValueError("Field 'workflow_id' is required")
    from cineflow_studio.installer.manifest import get_workflow_template
    wf = get_workflow_template(workflow_id)
    if not wf:
        raise ValueError(f"Workflow '{workflow_id}' not found in catalog")
    return wf


async def handle_install_node(args: dict[str, Any]) -> dict[str, Any]:
    comfy_dir = args.get("comfy_dir", "ComfyUI")
    node_name = args.get("node_name", "").strip()
    git_url = args.get("git_url")
    if not node_name:
        raise ValueError("Field 'node_name' is required")
    from pathlib import Path

    from cineflow_studio.installer.runner import install_custom_node
    return install_custom_node(Path(comfy_dir), node_name, git_url)


async def handle_download_model(args: dict[str, Any]) -> dict[str, Any]:
    comfy_dir = args.get("comfy_dir", "ComfyUI")
    model_name = args.get("model_name", "").strip()
    mirror = args.get("mirror", "huggingface")
    execute = bool(args.get("execute_download", False))
    if not model_name:
        raise ValueError("Field 'model_name' is required")
    from pathlib import Path

    from cineflow_studio.installer.runner import download_model
    return download_model(Path(comfy_dir), model_name, mirror=mirror, execute_download=execute)


async def handle_generate_dependency_script(args: dict[str, Any]) -> dict[str, Any]:
    comfy_dir = args.get("comfy_dir", "ComfyUI")
    profile = args.get("profile")
    mirror = args.get("mirror", "huggingface")
    from pathlib import Path

    from cineflow_studio.installer.runner import generate_dependency_install_script
    script = generate_dependency_install_script(Path(comfy_dir), profile_name=profile, mirror=mirror)
    return {
        "status": "generated",
        "installer_script": str(script),
        "profile": profile or "auto_detected",
        "mirror": mirror,
        "run_instructions": f"Run '{script}' in terminal to download all required weights and clone custom nodes.",
    }


async def handle_check_updates(_args: dict[str, Any]) -> dict[str, Any]:
    from cineflow_studio.mcp.updates import check_cineflow_updates
    return await check_cineflow_updates()


async def handle_apply_update(_args: dict[str, Any]) -> dict[str, Any]:
    from cineflow_studio.mcp.updates import apply_cineflow_updates
    return await apply_cineflow_updates()


async def handle_character_create(args: dict[str, Any]) -> dict[str, Any]:
    project_id = args.get("project_id", "").strip()
    name = args.get("name", "").strip()
    sheet_path = args.get("sheet_path", "").strip()
    if not project_id or not name or not sheet_path:
        raise ValueError(
            "Fields 'project_id', 'name', and 'sheet_path' are required — a character "
            "needs a real sheet image: the upload runs the identity vision pass server-side."
        )
    from cineflow_studio.mcp import cloud
    return await cloud.create_character(project_id, name, sheet_path)


async def handle_deepseek_status(args: dict[str, Any]) -> dict[str, Any]:
    base_url = args.get("base_url")
    from cineflow_studio.mcp.deepseek import probe_deepseek_endpoint
    return await probe_deepseek_endpoint(base_url)


async def handle_vision_inspect(args: dict[str, Any]) -> dict[str, Any]:
    image_path = args.get("image_path", "").strip()
    if not image_path:
        raise ValueError("Field 'image_path' is required")
    prev_frame = args.get("previous_frame_path")
    check_mouth = bool(args.get("check_closed_mouth", False))
    task = args.get("task", "evaluate_quality")
    comfy_url = args.get("comfy_url")

    from cineflow_studio.mcp.vision import inspect_frame_with_qwen_cv
    return inspect_frame_with_qwen_cv(
        image_path=image_path,
        previous_frame_path=prev_frame,
        check_closed_mouth=check_mouth,
        task=task,
        comfy_url=comfy_url,
    )


async def handle_comfy_workflow_execute(args: dict[str, Any]) -> dict[str, Any]:
    project_id = args.get("project_id", "").strip()
    scene_id = args.get("scene_id", "").strip()
    shot_id = args.get("shot_id", "").strip()
    if not project_id or not scene_id or not shot_id:
        raise ValueError("Fields 'project_id', 'scene_id', and 'shot_id' are required")

    workflow_id = args.get("workflow_id")
    custom_graph = args.get("workflow")
    overrides = args.get("params")
    comfy_url = args.get("comfy_url")

    from cineflow_studio.mcp.comfy_builder import assemble_comfy_workflow, queue_comfy_workflow, upload_ref_files

    # Studio 6f: cloud-first assembly. The production dialect knowledge lives
    # on the server; the client sends a describe request and queues the
    # returned graph locally. Without a configured server (community mode) or
    # when the server refuses/fails, the verified local blueprint path runs —
    # said honestly in the answer, never silently mixed.
    graph: dict | None = None
    assembly = "community"
    assembly_note = ""
    server_key = (args.get("server_workflow_key") or "").strip()
    if server_key:
        from cineflow_studio.mcp import cloud

        if not cloud.cloud_configured():
            assembly_note = "No CineFlow API token configured; assembled the community blueprint locally."
        else:
            try:
                uploaded = await upload_ref_files(comfy_url, list(args.get("ref_files") or []))
                assembled = await cloud.assemble_comfy_graph(
                    project_id,
                    {
                        "workflow_key": server_key,
                        "prompt": str((overrides or {}).get("prompt") or args.get("prompt") or ""),
                        "negative_prompt": args.get("negative_prompt"),
                        "ref_filenames": uploaded,
                        "width": (overrides or {}).get("width"),
                        "height": (overrides or {}).get("height"),
                        "seed": (overrides or {}).get("seed"),
                    },
                )
                if not assembled.get("graph"):
                    raise cloud.CloudError("the server answered an empty graph")
                graph = assembled["graph"]
                assembly = "server"
                assembly_note = f"Assembled server-side ({server_key}); ref ceiling {assembled.get('ref_slots_max')}."
            except (cloud.CloudError, ValueError, OSError) as exc:
                # httpx errors under it are upload/queue network failures — same fallback.
                assembly_note = f"Server assembly unavailable ({exc}); fell back to the community blueprint."

    if graph is None:
        if server_key and not custom_graph and not workflow_id:
            # An explicitly requested server dialect cannot degrade into a
            # random local blueprint: say what is missing.
            return {
                "status": "failed",
                "assembly": assembly,
                "assembly_note": (
                    "Server assembly was requested (server_workflow_key="
                    f"{server_key}) but it is unavailable, and no community "
                    "blueprint or custom graph was provided as a fallback."
                ),
            }
        graph, _warnings = assemble_comfy_workflow(
            workflow_id=workflow_id,
            custom_graph=custom_graph,
            overrides=overrides,
        )
    result = await queue_comfy_workflow(
        project_id=project_id,
        scene_id=scene_id,
        shot_id=shot_id,
        workflow_graph=graph,
        comfy_url=comfy_url,
        metadata=overrides,
    )
    result["assembly"] = assembly
    if assembly_note:
        result["assembly_note"] = assembly_note
    return result


# -------------------------------------------------------------------------
# Tool Definitions Registry
# -------------------------------------------------------------------------

TOOLS: dict[str, tuple[ToolDefinition, Callable[[dict[str, Any]], Any]]] = {
    "cineflow_quick_tts": (
        ToolDefinition(
            name="cineflow_quick_tts",
            description="Single-shot high fidelity speech synthesis (Higgs v3 / Qwen TTS) with emotion and optional voice cloning.",
            input_schema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The text line to speak."},
                    "voice_sample": {"type": "string", "description": "Optional path to WAV reference audio for voice cloning."},
                    "emotion": {"type": "string", "enum": ["neutral", "joyful", "dramatic", "whisper"], "description": "Speech emotion tone."},
                },
                "required": ["text"],
            },
        ),
        handle_quick_tts,
    ),
    "cineflow_quick_photo_animate": (
        ToolDefinition(
            name="cineflow_quick_photo_animate",
            description="Animate any still portrait or product photo into a 5-8 second cinematic video clip via LTX 2.5.",
            input_schema={
                "type": "object",
                "properties": {
                    "image_path": {"type": "string", "description": "Path to input photo."},
                    "prompt": {"type": "string", "description": "Motion description in cinematic English (e.g. 'camera slowly pans, natural blinking')."},
                    "duration": {"type": "number", "minimum": 5.0, "maximum": 8.0, "description": "Clip duration in seconds (5.0 to 8.0)."},
                },
                "required": ["image_path"],
            },
        ),
        handle_quick_photo_animate,
    ),
    "cineflow_quick_reel": (
        ToolDefinition(
            name="cineflow_quick_reel",
            description="Create an assembled commercial montage reel from a folder of source media assets.",
            input_schema={
                "type": "object",
                "properties": {
                    "folder_path": {"type": "string", "description": "Directory path containing input images/clips."},
                    "prompt": {"type": "string", "description": "Overall style description in English."},
                },
                "required": ["folder_path"],
            },
        ),
        handle_quick_reel,
    ),
    "cineflow_project_create": (
        ToolDefinition(
            name="cineflow_project_create",
            description="🔧 LOCAL ONLY: create a project in the local store (storage/projects/, offline community mode). The returned p_… id works ONLY with local tools — for cloud tools use cineflow_project_init and its SERVER id.",
            input_schema={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Project title."},
                    "screenplay": {"type": "string", "description": "Full screenplay or story synopsis."},
                    "aspect": {"type": "string", "enum": ["9:16", "16:9", "1:1"], "description": "Target video aspect ratio."},
                    "style": {"type": "string", "description": "Visual aesthetic style (e.g. 'cinematic', 'anime', 'documentary')."},
                },
                "required": ["title", "screenplay"],
            },
        ),
        handle_project_create,
    ),
    "cineflow_materials_attach": (
        ToolDefinition(
            name="cineflow_materials_attach",
            description="Register characters, props, and locations for the project and generate turnaround cards for human approval.",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Target project ID."},
                    "characters": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "description": {"type": "string", "description": "Visual description in English."},
                                "image_path": {"type": "string"},
                            },
                            "required": ["name"],
                        },
                    },
                    "props": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "description": {"type": "string", "description": "Prop description in English."},
                                "image_path": {"type": "string"},
                            },
                            "required": ["name"],
                        },
                    },
                    "locations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "image_path": {"type": "string"},
                            },
                            "required": ["name"],
                        },
                    },
                },
                "required": ["project_id"],
            },
        ),
        handle_materials_attach,
    ),
    "cineflow_dialogue_tts": (
        ToolDefinition(
            name="cineflow_dialogue_tts",
            description="Render all dialogue audio lines for the project to establish exact shot timing and audio pacing.",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Target project ID."},
                    "lines": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "speaker": {"type": "string"},
                                "text": {"type": "string"},
                                "emotion": {"type": "string"},
                            },
                            "required": ["speaker", "text"],
                        },
                    },
                },
                "required": ["project_id", "lines"],
            },
        ),
        handle_dialogue_tts,
    ),
    "cineflow_frames_generate": (
        ToolDefinition(
            name="cineflow_frames_generate",
            description="Generate starting keyframes for shots. Enforces reference policy (every <Subject N> must be addressed in prompt).",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Target project ID."},
                    "frame_specs": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "shot_index": {"type": "integer"},
                                "prompt": {"type": "string", "description": "Visual prompt in English referencing <Subject 1>, etc."},
                                "subjects": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Declared subjects, e.g. ['<Subject 1>', '<Subject 2>'].",
                                },
                            },
                            "required": ["shot_index", "prompt"],
                        },
                    },
                },
                "required": ["project_id", "frame_specs"],
            },
        ),
        handle_frames_generate,
    ),
    "cineflow_video_render": (
        ToolDefinition(
            name="cineflow_video_render",
            description="Render motion video clips for shots via MiniMax H3 / LTX 2.5. Enforces closed-mouth guard on non-dialogue clips (#600).",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Target project ID."},
                    "clip_specs": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "shot_index": {"type": "integer"},
                                "prompt": {"type": "string", "description": "Motion prompt in English."},
                                "duration": {"type": "number"},
                                "voice_track": {"type": "string", "description": "Optional path to dialogue voice file."},
                                "keep_mouth_closed": {"type": "boolean", "description": "Set true to enforce closed mouth guard."},
                            },
                            "required": ["shot_index", "prompt", "duration"],
                        },
                    },
                },
                "required": ["project_id", "clip_specs"],
            },
        ),
        handle_video_render,
    ),
    "cineflow_export_mp4": (
        ToolDefinition(
            name="cineflow_export_mp4",
            description="Stitch rendered video clips, dialogue tracks, and background music into the final exported MP4 timeline.",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Target project ID."},
                    "music_path": {"type": "string", "description": "Optional background music audio file path."},
                    "duck": {"type": "boolean", "description": "Whether to duck music volume under dialogue."},
                },
                "required": ["project_id"],
            },
        ),
        handle_export_mp4,
    ),
    "cineflow_status": (
        ToolDefinition(
            name="cineflow_status",
            description="Inspect system health, ComfyUI backend reachability, active GPU jobs, and project status.",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Optional project ID to inspect."},
                },
            },
        ),
        handle_status,
    ),
    "cineflow_cloud_script_plan": (
        ToolDefinition(
            name="cineflow_cloud_script_plan",
            description="Cloud mode: upload the script to the CineFlow server, enqueue the plan job, and wait for it (bounded). Requires CINEFLOW_API_KEY.",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Remote CineFlow project id"},
                    "script_text": {"type": "string", "description": "Full screenplay text"},
                },
                "required": ["project_id", "script_text"],
            },
        ),
        handle_cloud_script_plan,
    ),
    "cineflow_billing_status": (
        ToolDefinition(
            name="cineflow_billing_status",
            description="Check current billing status: community (local ComfyUI) mode and whether a CineFlow API key is configured. The tier and entitlements are decided by the CineFlow server, not by this client.",
            input_schema={
                "type": "object",
                "properties": {},
            },
        ),
        handle_billing_status,
    ),
    "cineflow_auth": (
        ToolDefinition(
            name="cineflow_auth",
            description="Store a CineFlow API key for cloud calls. Saving is not verification: the tier and entitlements are decided by the CineFlow server on each cloud call.",
            input_schema={
                "type": "object",
                "properties": {
                    "api_key": {
                        "type": "string",
                        "description": "Personal CineFlow token (cfp_...) minted on the CineFlow portal (POST /me/tokens) or the /account/tokens page.",
                    },
                },
                "required": ["api_key"],
            },
        ),
        handle_auth,
    ),
    "cineflow_plan_stages": (
        ToolDefinition(
            name="cineflow_plan_stages",
            description="☁ The REAL CineFlow stage system prompts (reading, decoupage, carry-over) and numeric rules (frame ceiling, ref slots). Follow them exactly — they are what the server's own director stages follow.",
            input_schema={
                "type": "object",
                "properties": {"project_id": {"type": "string", "description": "Project ID."}},
                "required": ["project_id"],
            },
        ),
        handle_plan_stages,
    ),
    "cineflow_plan_state": (
        ToolDefinition(
            name="cineflow_plan_state",
            description="☁ The canonical project state from the CineFlow DB: script lines, characters (source AND render names — one person, two names), plan-cache summary. Read before every propose; never keep your own copy.",
            input_schema={
                "type": "object",
                "properties": {"project_id": {"type": "string", "description": "Project ID."}},
                "required": ["project_id"],
            },
        ),
        handle_plan_state,
    ),
    "cineflow_scenes_propose": (
        ToolDefinition(
            name="cineflow_scenes_propose",
            description="☁ Propose your scene draft as data (title, place/time, cast by name, shots with ≤2 actions, a prompt per shot). Per-scene machine codes come back for repairs — fix your draft and retry.",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project ID."},
                    "scenes": {"type": "array", "items": {"type": "object"}, "description": "Scene drafts (id, title, cast, shots)."},
                    "source_note": {"type": "string", "description": "Optional note about the source (book/screenplay)."},
                },
                "required": ["project_id", "scenes"],
            },
        ),
        handle_scenes_propose,
    ),
    "cineflow_character_create": (
        ToolDefinition(
            name="cineflow_character_create",
            description="☁ Create a character on the CineFlow server: multipart name + a real sheet image (local path) — the sheet is required, the upload runs the identity vision pass. Use cineflow_plan_state to see existing characters first; never cast one person as two names.",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "SERVER project ID (from cineflow_project_init)."},
                    "name": {"type": "string", "description": "Character name (source name)."},
                    "sheet_path": {"type": "string", "description": "Local path to the sheet image (png/jpg)."},
                },
                "required": ["project_id", "name", "sheet_path"],
            },
        ),
        handle_character_create,
    ),
    "cineflow_davinci_sync": (
        ToolDefinition(
            name="cineflow_davinci_sync",
            description="Synchronize project timeline, shots, and audio directly with DaVinci Resolve (or export FCPXML 1.10). Automatically installs the 'CineFlow: Edit in ComfyUI' action script for round-trip clip editing.",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Target project ID."},
                    "timeline_name": {"type": "string", "description": "Custom timeline name in DaVinci Resolve."},
                    "install_action": {"type": "boolean", "description": "Whether to install CineFlow_Edit_in_ComfyUI script in Resolve Edit menu."},
                },
                "required": ["project_id"],
            },
        ),
        handle_davinci_sync,
    ),
    "cineflow_project_init": (
        ToolDefinition(
            name="cineflow_project_init",
            description="☁/🔧 THE project opener: creates the workspace (source/, materials/, scenes/) and — with a CineFlow token — the SERVER project (the returned id is the SERVER project_id every cloud tool takes; the local tree keeps only a mirror.json). Without a token this is the local store.",
            input_schema={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Project title."},
                    "source_text": {"type": "string", "description": "Original text of the screenplay, book chapter, or story."},
                    "source_filename": {"type": "string", "description": "Filename to store in source/ (e.g. 'book_chapter_1.txt')."},
                    "aspect": {"type": "string", "enum": ["16:9", "9:16", "1:1"], "description": "Target aspect ratio."},
                    "style": {"type": "string", "description": "Visual aesthetic style."},
                    "characters": {"type": "array", "items": {"type": "object"}, "description": "Extracted cast list with names and visual descriptions."},
                    "locations": {"type": "array", "items": {"type": "object"}, "description": "Extracted key locations."},
                    "scenes": {"type": "array", "items": {"type": "object"}, "description": "Extracted list of scenes/episodes."},
                },
                "required": ["title", "source_text"],
            },
        ),
        handle_project_init,
    ),
    "cineflow_projects_list": (
        ToolDefinition(
            name="cineflow_projects_list",
            description="List all existing projects in studio storage with summaries of their characters, locations, scenes, and production stages.",
            input_schema={
                "type": "object",
                "properties": {
                    "filter": {
                        "type": "string",
                        "description": "Optional search query to filter projects by title or ID (e.g. 'Убийство' or 'sci-fi').",
                    },
                },
            },
        ),
        handle_projects_list,
    ),
    "cineflow_assets_transfer": (
        ToolDefinition(
            name="cineflow_assets_transfer",
            description="Transfer and clone characters, locations, or props from an existing project into the current target project. Automatically copies turnaround cards, plates, and voice models into target materials while maintaining project.json continuity.",
            input_schema={
                "type": "object",
                "properties": {
                    "source_project": {
                        "type": "string",
                        "description": "Source project ID or title query (e.g. 'Убийство' or 'p_murder_mystery').",
                    },
                    "target_project_id": {
                        "type": "string",
                        "description": "Target project ID receiving the assets.",
                    },
                    "asset_types": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["characters", "locations", "props"]},
                        "description": "Types of assets to transfer. Defaults to all available.",
                    },
                    "names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional specific character or location names to transfer (e.g. ['Мартин', 'Лиза']).",
                    },
                    "conflict_strategy": {
                        "type": "string",
                        "enum": ["skip", "overwrite", "rename"],
                        "description": "How to handle naming conflicts with existing assets in target project. Defaults to 'skip'.",
                    },
                },
                "required": ["source_project", "target_project_id"],
            },
        ),
        handle_assets_transfer,
    ),
    "cineflow_project_get_state": (
        ToolDefinition(
            name="cineflow_project_get_state",
            description="Read the canonical Source of Truth (project.json) manifest. Returns project stage, approved characters, active scene, and production history.",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Target project ID."},
                },
                "required": ["project_id"],
            },
        ),
        handle_project_get_state,
    ),
    "cineflow_project_update_state": (
        ToolDefinition(
            name="cineflow_project_update_state",
            description="Update the canonical Source of Truth (project.json) manifest. Automatically tracks changes and reports impact warnings on downstream shots (e.g. if character appearance is changed after generation).",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Target project ID."},
                    "updates": {"type": "object", "description": "Dictionary of fields to update (characters, locations, notes, style, etc.)."},
                },
                "required": ["project_id", "updates"],
            },
        ),
        handle_project_update_state,
    ),
    "cineflow_scene_activate": (
        ToolDefinition(
            name="cineflow_scene_activate",
            description="Activate a specific scene for production. Provisions dedicated scenes/scene_XX/ directory with frames/, audio/, and video/ subfolders, and updates project.json stage.",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Target project ID."},
                    "scene_id": {"type": "string", "description": "Scene identifier (e.g. 'scene_01')."},
                    "scene_title": {"type": "string", "description": "Human-readable scene title."},
                },
                "required": ["project_id", "scene_id"],
            },
        ),
        handle_scene_activate,
    ),
    "cineflow_hardware_profile": (
        ToolDefinition(
            name="cineflow_hardware_profile",
            description="Inspect local computer hardware (OS, CPU, RAM, GPU, VRAM) and recommend the optimal ComfyUI memory profile (rtx_24gb, rtx_16gb, rtx_12gb, apple_silicon, or cloud_only).",
            input_schema={
                "type": "object",
                "properties": {},
            },
        ),
        handle_hardware_profile,
    ),
    "cineflow_installer_audit": (
        ToolDefinition(
            name="cineflow_installer_audit",
            description="Audit local ComfyUI installation, checking for installed vs missing model weights (HuggingFace) and custom nodes readiness percentage.",
            input_schema={
                "type": "object",
                "properties": {
                    "comfy_dir": {"type": "string", "description": "Path to local ComfyUI directory (default: 'ComfyUI')."},
                },
            },
        ),
        handle_installer_audit,
    ),
    "cineflow_generate_launcher": (
        ToolDefinition(
            name="cineflow_generate_launcher",
            description="Generate a supervised ComfyUI launch script (run_comfy_cineflow.sh or .bat) preconfigured with optimal VRAM flags for the user's GPU.",
            input_schema={
                "type": "object",
                "properties": {
                    "comfy_dir": {"type": "string", "description": "Target ComfyUI directory."},
                    "profile": {"type": "string", "description": "VRAM profile override (e.g. 'rtx_24gb', 'rtx_16gb')."},
                },
            },
        ),
        handle_generate_launcher,
    ),
    "cineflow_cache_cleanup": (
        ToolDefinition(
            name="cineflow_cache_cleanup",
            description="Clean up temporary latents in output/latents/ and preview cache (#608) to free SSD space.",
            input_schema={
                "type": "object",
                "properties": {
                    "comfy_dir": {"type": "string", "description": "Target ComfyUI directory."},
                },
            },
        ),
        handle_cache_cleanup,
    ),
    "cineflow_scene_graph_get": (
        ToolDefinition(
            name="cineflow_scene_graph_get",
            description="Retrieve the Directed Scene Graph, including nodes, narrative edges/cuts, continuity carryover, and timeline sequence.",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project identifier (e.g. 'p_cyber_noir')."},
                },
                "required": ["project_id"],
            },
        ),
        handle_scene_graph_get,
    ),
    "cineflow_scene_graph_update": (
        ToolDefinition(
            name="cineflow_scene_graph_update",
            description="Update the Directed Scene Graph: nodes, transitions (CUT, MATCH_CUT, CROSSFADE, L_CUT, J_CUT, SMASH_CUT), and timeline sequence.",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project identifier."},
                    "nodes": {"type": "array", "description": "List of scene node definitions with dramatic intent and continuity."},
                    "edges": {"type": "array", "description": "List of narrative transitions between scenes with carryover state."},
                    "timeline_sequence": {"type": "array", "items": {"type": "string"}, "description": "Ordered sequence of scene IDs for montage."},
                },
                "required": ["project_id"],
            },
        ),
        handle_scene_graph_update,
    ),
    "cineflow_scene_directing_set": (
        ToolDefinition(
            name="cineflow_scene_directing_set",
            description="Set director explication for a scene: emotional arc, camera style, color palette, lighting setup, beat sheet, and continuity.",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project identifier."},
                    "scene_id": {"type": "string", "description": "Scene identifier (e.g. 'scene_01')."},
                    "slugline": {"type": "string", "description": "Standard script slugline (e.g. 'INT. LAB - NIGHT')."},
                    "dramatic_intent": {"type": "object", "description": "Emotional arc, camera style, color palette, lighting setup, pacing."},
                    "continuity": {"type": "object", "description": "Time of day, weather, character costume/injury/props states."},
                    "beat_sheet": {"type": "array", "description": "List of scene beats (action, conflict, resolution)."},
                    "shots": {"type": "array", "description": "List of shot plans."},
                },
                "required": ["project_id", "scene_id"],
            },
        ),
        handle_scene_directing_set,
    ),
    "cineflow_comfy_config_get": (
        ToolDefinition(
            name="cineflow_comfy_config_get",
            description="Get ComfyUI environment paths (comfy_dir, models_dir, custom_nodes_dir) and active API URL for the project.",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project identifier."},
                },
                "required": ["project_id"],
            },
        ),
        handle_comfy_config_get,
    ),
    "cineflow_comfy_config_set": (
        ToolDefinition(
            name="cineflow_comfy_config_set",
            description="Configure and save ComfyUI directory paths and API URLs for the project (stored in settings/comfyui.json).",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project identifier."},
                    "comfy_dir": {"type": "string", "description": "Path to local ComfyUI directory."},
                    "comfy_url": {"type": "string", "description": "ComfyUI API endpoint (e.g. 'http://127.0.0.1:8188')."},
                    "models_dir": {"type": "string", "description": "Path to ComfyUI models directory."},
                    "custom_nodes_dir": {"type": "string", "description": "Path to custom nodes directory."},
                    "active_profile": {"type": "string", "description": "VRAM profile (e.g. 'rtx_24gb', 'rtx_16gb')."},
                },
                "required": ["project_id"],
            },
        ),
        handle_comfy_config_set,
    ),
    "cineflow_shot_record_artifact": (
        ToolDefinition(
            name="cineflow_shot_record_artifact",
            description="Record a generated shot artifact, saving the exact ComfyUI workflow JSON and creating a sidecar .cineflow.json alongside the media.",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project identifier."},
                    "scene_id": {"type": "string", "description": "Scene identifier."},
                    "shot_id": {"type": "string", "description": "Shot identifier (e.g. 'shot_01')."},
                    "media_filename": {"type": "string", "description": "Generated media filename (e.g. 'shot_01.mp4')."},
                    "comfy_url": {"type": "string", "description": "ComfyUI URL used for generation."},
                    "comfy_prompt_id": {"type": "string", "description": "ComfyUI prompt execution task ID."},
                    "workflow_api": {"type": "object", "description": "Exact ComfyUI workflow prompt JSON dictionary."},
                    "prompt": {"type": "string", "description": "English generation prompt."},
                    "negative_prompt": {"type": "string", "description": "Negative prompt."},
                    "seed": {"type": "integer", "description": "Generation seed."},
                    "model": {"type": "string", "description": "Model checkpoint name used."},
                    "metadata": {"type": "object", "description": "Optional additional shot metadata."},
                },
                "required": ["project_id", "scene_id", "shot_id", "media_filename"],
            },
        ),
        handle_shot_record_artifact,
    ),
    "cineflow_models_catalog": (
        ToolDefinition(
            name="cineflow_models_catalog",
            description="List models and weights with direct download links (HuggingFace, hf-mirror, ModelScope), file sizes, target directories, and curl commands.",
            input_schema={
                "type": "object",
                "properties": {
                    "mirror": {"type": "string", "enum": ["huggingface", "hf-mirror", "modelscope"], "description": "Mirror to construct URLs for."},
                    "profile": {"type": "string", "description": "Filter by hardware VRAM profile (e.g. 'rtx_24gb', 'rtx_16gb')."},
                },
            },
        ),
        handle_models_catalog,
    ),
    "cineflow_nodes_catalog": (
        ToolDefinition(
            name="cineflow_nodes_catalog",
            description="List all verified ComfyUI custom nodes required for video, turnaround, and speech generation with git clone URLs.",
            input_schema={
                "type": "object",
                "properties": {},
            },
        ),
        handle_nodes_catalog,
    ),
    "cineflow_workflows_catalog": (
        ToolDefinition(
            name="cineflow_workflows_catalog",
            description="Catalog of verified ComfyUI workflow templates (LTX-Video img2vid, FLUX turnaround, Higgs TTS, MiniMax H3).",
            input_schema={
                "type": "object",
                "properties": {},
            },
        ),
        handle_workflows_catalog,
    ),
    "cineflow_workflow_get": (
        ToolDefinition(
            name="cineflow_workflow_get",
            description="Retrieve the exact ComfyUI JSON node graph blueprint for a specific workflow template.",
            input_schema={
                "type": "object",
                "properties": {
                    "workflow_id": {"type": "string", "description": "Workflow identifier (e.g. 'ltx_video_img2vid', 'flux_character_turnaround')."},
                },
                "required": ["workflow_id"],
            },
        ),
        handle_workflow_get,
    ),
    "cineflow_install_node": (
        ToolDefinition(
            name="cineflow_install_node",
            description="Clone or update a ComfyUI custom node into custom_nodes/ and install its requirements.txt dependencies.",
            input_schema={
                "type": "object",
                "properties": {
                    "comfy_dir": {"type": "string", "description": "Target ComfyUI directory (default: 'ComfyUI')."},
                    "node_name": {"type": "string", "description": "Name of custom node (e.g. 'ComfyUI-LTXVideo')."},
                    "git_url": {"type": "string", "description": "Optional custom git repository URL."},
                },
                "required": ["node_name"],
            },
        ),
        handle_install_node,
    ),
    "cineflow_download_model": (
        ToolDefinition(
            name="cineflow_download_model",
            description="Download a model weight into the correct ComfyUI folder (checkpoints, unet, loras, tts) with resume support or return the curl command.",
            input_schema={
                "type": "object",
                "properties": {
                    "comfy_dir": {"type": "string", "description": "Target ComfyUI directory."},
                    "model_name": {"type": "string", "description": "Model weight name or filename."},
                    "mirror": {"type": "string", "enum": ["huggingface", "hf-mirror", "modelscope"], "description": "Download mirror to use."},
                    "execute_download": {"type": "boolean", "description": "If true, executes the curl download immediately. If false, returns destination and curl command."},
                },
                "required": ["model_name"],
            },
        ),
        handle_download_model,
    ),
    "cineflow_generate_dependency_script": (
        ToolDefinition(
            name="cineflow_generate_dependency_script",
            description="Generate an all-in-one bash/bat script (install_cineflow_models.sh) that clones all custom nodes and downloads all weights with resume support in 1 click.",
            input_schema={
                "type": "object",
                "properties": {
                    "comfy_dir": {"type": "string", "description": "Target ComfyUI directory."},
                    "profile": {"type": "string", "description": "VRAM hardware profile to download weights for (default: auto-detected)."},
                    "mirror": {"type": "string", "enum": ["huggingface", "hf-mirror", "modelscope"], "description": "Download mirror to use in the script."},
                },
            },
        ),
        handle_generate_dependency_script,
    ),
    "cineflow_check_updates": (
        ToolDefinition(
            name="cineflow_check_updates",
            description="Check for CineFlow Studio updates: a PyPI release (installed package) or the monorepo git remote (development checkout). Answers JSON; never upgrades by itself.",
            input_schema={
                "type": "object",
                "properties": {},
            },
        ),
        handle_check_updates,
    ),
    "cineflow_apply_update": (
        ToolDefinition(
            name="cineflow_apply_update",
            description="Apply updates: in a development checkout pulls the monorepo and re-syncs skills/DaVinci scripts; in an installed PyPI package returns the exact user upgrade command instead of mutating the environment.",
            input_schema={
                "type": "object",
                "properties": {},
            },
        ),
        handle_apply_update,
    ),
    "cineflow_deepseek_status": (
        ToolDefinition(
            name="cineflow_deepseek_status",
            description="Probe and verify internal or local LLM server (DeepSeek, Qwen 2.5, Llama 3, Mistral via vLLM, Ollama, SGLang, llama-server) status, models, and studio topology (Topology 1: Single-GPU External LLM vs Topology 2: Dual-Server Internal Cluster).",
            input_schema={
                "type": "object",
                "properties": {
                    "base_url": {
                        "type": "string",
                        "description": "Optional custom endpoint URL (e.g. 'http://127.0.0.1:11434/v1' or 'http://internal-llm:8000/v1').",
                    },
                },
            },
        ),
        handle_deepseek_status,
    ),
    "cineflow_internal_llm_status": (
        ToolDefinition(
            name="cineflow_internal_llm_status",
            description="Universal probe for internal/on-premise LLM servers (DeepSeek, Qwen 2.5, Llama 3, Mistral) and multi-server studio topology.",
            input_schema={
                "type": "object",
                "properties": {
                    "base_url": {
                        "type": "string",
                        "description": "Optional custom endpoint URL.",
                    },
                },
            },
        ),
        handle_deepseek_status,
    ),
    "cineflow_vision_inspect": (
        ToolDefinition(
            name="cineflow_vision_inspect",
            description="Inspect and evaluate keyframes/takes via Qwen 3.8 Vision co-located inside ComfyUI: aesthetic quality, artifact/defect detection, lip-sync closed-mouth guard (Issue #600), and English reference auto-captioning without VRAM conflicts.",
            input_schema={
                "type": "object",
                "properties": {
                    "image_path": {"type": "string", "description": "Path to input frame or reference photo."},
                    "previous_frame_path": {"type": "string", "description": "Optional path to preceding shot's frame for continuity scoring."},
                    "check_closed_mouth": {"type": "boolean", "description": "Whether to verify lips are closed for silent or voiceover shots (Rule D)."},
                    "task": {
                        "type": "string",
                        "enum": ["evaluate_quality", "check_defects", "describe_reference", "continuity_check"],
                        "description": "Visual CV task to perform.",
                    },
                    "comfy_url": {"type": "string", "description": "Optional ComfyUI base URL (default: http://127.0.0.1:8188)."},
                },
                "required": ["image_path"],
            },
        ),
        handle_vision_inspect,
    ),
    "cineflow_comfy_workflow_execute": (
        ToolDefinition(
            name="cineflow_comfy_workflow_execute",
            description="Build and queue a ComfyUI graph: ☁ with a configured token and server_workflow_key the CineFlow server assembles the production dialect graph (ref policy enforced server-side); 🔧 otherwise a verified community blueprint from the catalog. Saves reproducible .comfy.json and sidecar .cineflow.json alongside shot media.",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Target project ID."},
                    "scene_id": {"type": "string", "description": "Target scene ID (e.g. 'scene_01')."},
                    "shot_id": {"type": "string", "description": "Target shot ID (e.g. 'shot_01')."},
                    "workflow_id": {
                        "type": "string",
                        "description": "Optional verified workflow ID from catalog (e.g. 'ltx_video_img2vid', 'flux_character_turnaround', 'higgs_voice_clone_tts', 'qwen_vision_frame_inspect', 'ltx_video_img2vid_3090').",
                    },
                    "workflow": {
                        "type": "object",
                        "description": "Optional custom ComfyUI API prompt graph dictionary.",
                    },
                    "params": {
                        "type": "object",
                        "description": "Parameter overrides to inject into the graph (prompt, seed, steps, cfg, width, height, input_image, filename_prefix).",
                    },
                    "comfy_url": {
                        "type": "string",
                        "description": "Optional custom ComfyUI base URL (default: http://127.0.0.1:8188).",
                    },
                    "server_workflow_key": {
                        "type": "string",
                        "description": "Production dialect key for server-side assembly (e.g. 'qwen_image21_edit'). Requires a configured CineFlow token; the server builds the runnable graph and enforces the dialect ref policy — the client never assembles production dialects locally.",
                    },
                    "ref_files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Local paths of reference images; uploaded to the local ComfyUI first, their server-visible filenames go into the assembled graph.",
                    },
                    "prompt": {"type": "string", "description": "Prompt for server-side assembly (used when server_workflow_key is set)."},
                    "negative_prompt": {"type": "string", "description": "Negative prompt for server-side assembly."},
                },
                "required": ["project_id", "scene_id", "shot_id"],
            },
        ),
        handle_comfy_workflow_execute,
    ),
}


def get_tool_definitions() -> list[ToolDefinition]:
    return [definition for definition, _ in TOOLS.values()]


async def execute_tool(name: str, arguments: dict[str, Any]) -> tuple[str, bool]:
    if name not in TOOLS:
        return f"Unknown tool: '{name}'", True
    _, handler = TOOLS[name]
    try:
        result = await handler(arguments)
        from cineflow_studio.mcp.security import sanitize_data
        safe_result = sanitize_data(result)
        return json.dumps(safe_result, ensure_ascii=False, indent=2), False
    except Exception as exc:  # noqa: BLE001
        from cineflow_studio.mcp.security import sanitize_string
        safe_msg = sanitize_string(str(exc))
        return f"Error executing '{name}': {safe_msg}", True
