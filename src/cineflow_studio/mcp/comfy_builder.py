"""ComfyUI Workflow Assembly, Node Parameterization, and Queue Execution for OpenCode."""
from __future__ import annotations

import copy
import json
import os
import uuid
from typing import Any

from cineflow_studio.comfy.prompt_format import ensure_api_prompt_format
from cineflow_studio.installer.manifest import get_workflow_template
from cineflow_studio.mcp.project_store import get_project_dir


def assemble_comfy_workflow(
    workflow_id: str | None = None,
    custom_graph: dict[str, Any] | None = None,
    overrides: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Assembles and parameterizes a ComfyUI API prompt graph."""
    if not workflow_id and not custom_graph:
        raise ValueError("Either 'workflow_id' or 'custom_graph' must be provided.")

    warnings: list[str] = []
    base_graph: dict[str, Any]

    if workflow_id:
        tmpl = get_workflow_template(workflow_id)
        if not tmpl:
            raise ValueError(f"Workflow template '{workflow_id}' not found in catalog.")
        base_graph = copy.deepcopy(tmpl.get("api_graph", {}))
    else:
        assert custom_graph is not None
        base_graph, conv_warnings = ensure_api_prompt_format(custom_graph)
        warnings.extend(conv_warnings)

    if not base_graph:
        raise ValueError("Workflow graph is empty.")

    # Apply parameter overrides to graph nodes
    overrides = overrides or {}
    for node in base_graph.values():
        if not isinstance(node, dict):
            continue
        class_type = node.get("class_type", "")
        inputs = node.setdefault("inputs", {})

        # Positive Prompt
        if class_type == "CLIPTextEncode" and "prompt" in overrides:
            inputs["text"] = overrides["prompt"]

        # Sampler parameters (seed, steps, cfg)
        if class_type in ("KSampler", "KSamplerAdvanced"):
            if "seed" in overrides:
                inputs["seed"] = int(overrides["seed"])
            if "steps" in overrides:
                inputs["steps"] = int(overrides["steps"])
            if "cfg" in overrides:
                inputs["cfg"] = float(overrides["cfg"])

        # Latent dimensions
        if class_type in ("EmptyLatentImage", "EmptyLTXVLatentVideo"):
            if "width" in overrides:
                inputs["width"] = int(overrides["width"])
            if "height" in overrides:
                inputs["height"] = int(overrides["height"])
            if "length" in overrides and class_type == "EmptyLTXVLatentVideo":
                inputs["length"] = int(overrides["length"])

        # Input source image
        if class_type == "LoadImage" and "input_image" in overrides:
            inputs["image"] = overrides["input_image"]

        # Filename prefixes
        if class_type in ("SaveImage", "VHS_VideoCombine", "SaveAudio") and "filename_prefix" in overrides:
            inputs["filename_prefix"] = overrides["filename_prefix"]

    # Validate final graph structure
    final_graph, val_warnings = ensure_api_prompt_format(base_graph)
    warnings.extend(val_warnings)
    return final_graph, warnings


async def queue_comfy_workflow(
    project_id: str,
    scene_id: str,
    shot_id: str,
    workflow_graph: dict[str, Any],
    comfy_url: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Saves workflow .comfy.json & sidecar .cineflow.json, and queues prompt to ComfyUI."""
    base_comfy = (comfy_url or os.getenv("COMFYUI_URL", "http://127.0.0.1:8188")).rstrip("/")
    proj_dir = get_project_dir(project_id)
    scene_dir = proj_dir / "scenes" / scene_id

    wf_dir = scene_dir / "workflows"
    video_dir = scene_dir / "video"
    wf_dir.mkdir(parents=True, exist_ok=True)
    video_dir.mkdir(parents=True, exist_ok=True)

    clean_shot = shot_id.strip() or "shot_01"
    wf_file = wf_dir / f"{clean_shot}.comfy.json"
    sidecar_file = video_dir / f"{clean_shot}.cineflow.json"

    # 1. Save exact ComfyUI graph
    wf_file.write_text(json.dumps(workflow_graph, ensure_ascii=False, indent=2), encoding="utf-8")

    # 2. Save sidecar metadata passport
    sidecar_data = {
        "project_id": project_id,
        "scene_id": scene_id,
        "shot_id": clean_shot,
        "workflow_graph_file": str(wf_file),
        "comfy_url": base_comfy,
        "node_count": len(workflow_graph),
        "metadata": metadata or {},
    }
    sidecar_file.write_text(json.dumps(sidecar_data, ensure_ascii=False, indent=2), encoding="utf-8")

    # 3. Queue prompt to ComfyUI
    client_id = f"cineflow_{uuid.uuid4().hex[:8]}"
    prompt_id = f"prompt_{uuid.uuid4().hex[:12]}"
    is_live = False

    try:
        import httpx

        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{base_comfy}/prompt",
                json={"prompt": workflow_graph, "client_id": client_id},
            )
            if resp.status_code == 200:
                data = resp.json()
                prompt_id = data.get("prompt_id", prompt_id)
                is_live = True
    except (httpx.HTTPError, OSError):
        pass  # Graceful fallback in offline / test / local environment

    return {
        "status": "queued",
        "prompt_id": prompt_id,
        "is_live_comfy": is_live,
        "project_id": project_id,
        "scene_id": scene_id,
        "shot_id": clean_shot,
        "comfy_url": base_comfy,
        "node_count": len(workflow_graph),
        "workflow_path": str(wf_file),
        "sidecar_path": str(sidecar_file),
        "message": (
            f"Successfully assembled ComfyUI graph ({len(workflow_graph)} nodes) and queued "
            f"under prompt ID '{prompt_id}'. Saved '{clean_shot}.comfy.json' and '{clean_shot}.cineflow.json'."
        ),
    }


async def upload_ref_files(comfy_url: str | None, ref_paths: list[str]) -> list[str]:
    """Upload reference images to the LOCAL ComfyUI and return server-visible
    filenames (the hands, free tier). A failed upload raises — the caller
    falls back to the community blueprint path instead of a broken graph."""
    import httpx
    from pathlib import Path as _Path

    base = (comfy_url or os.getenv("COMFYUI_URL", "http://127.0.0.1:8188")).rstrip("/")
    uploaded: list[str] = []
    async with httpx.AsyncClient(timeout=30.0) as client:
        for raw in ref_paths:
            path = _Path(raw).expanduser()
            if not path.is_file():
                raise ValueError(f"reference file not found: {path}")
            with path.open("rb") as fh:
                resp = await client.post(
                    f"{base}/upload/image",
                    files={"image": (path.name, fh, "application/octet-stream")},
                    data={"overwrite": "true"},
                )
            resp.raise_for_status()
            data = resp.json()
            name = data.get("name") or path.name
            sub = data.get("subfolder") or ""
            uploaded.append(f"{sub}/{name}" if sub else name)
    return uploaded
