"""Internal & Local LLM endpoint probe and multi-server topology coordinator.

Supports two studio deployment topologies:
- Topology 1 (Single Server / 1 GPU Box):
    Agent LLM is external / subscription / IDE API (Codex, Cursor, Kimi Code, Claude Code).
    1 GPU (RTX 4090 / 3090) is 100% dedicated to ComfyUI (LTX-Video, FLUX, Qwen Vision CV, Higgs TTS).
- Topology 2 (Dual Server / Internal Cluster):
    Server A: Internal LLM Server (DeepSeek-R1, Qwen 2.5, Llama 3, Mistral via vLLM / Ollama).
    Server B: Dedicated ComfyUI Media Generation GPU Box.
"""
from __future__ import annotations

import os
import time
from typing import Any

import httpx

DEFAULT_ENDPOINTS = [
    "http://127.0.0.1:11434/v1",  # Ollama
    "http://127.0.0.1:8000/v1",   # vLLM / SGLang
    "http://127.0.0.1:8080/v1",
    "http://127.0.0.1:1234/v1",   # LMStudio
]


async def probe_deepseek_endpoint(base_url: str | None = None, timeout: float = 3.0) -> dict[str, Any]:
    """Probes an internal or local LLM endpoint (DeepSeek, Qwen, Llama, Mistral) and reports topology."""
    return await probe_internal_llm_endpoint(base_url=base_url, timeout=timeout)


async def probe_internal_llm_endpoint(base_url: str | None = None, timeout: float = 3.0) -> dict[str, Any]:
    """Universal probe for internal OpenAI-compatible LLM servers and studio topologies."""
    endpoints_to_try = [base_url] if base_url else [
        os.getenv("INTERNAL_LLM_URL"),
        os.getenv("DEEPSEEK_BASE_URL"),
        os.getenv("LOCAL_LLM_URL"),
        *DEFAULT_ENDPOINTS,
    ]
    endpoints_to_try = [e.rstrip("/") for e in endpoints_to_try if e]

    comfy_url = os.getenv("COMFYUI_URL", "http://127.0.0.1:8188")

    async with httpx.AsyncClient(timeout=timeout) as client:
        for ep in endpoints_to_try:
            url = f"{ep}/models"
            t0 = time.perf_counter()
            try:
                resp = await client.get(url)
                latency_ms = round((time.perf_counter() - t0) * 1000, 1)
                if resp.status_code == 200:
                    data = resp.json()
                    model_list = [m.get("id") for m in data.get("data", []) if isinstance(m, dict)]

                    # Categorize detected internal models
                    deepseek_models = [m for m in model_list if "deepseek" in str(m).lower()]
                    qwen_models = [m for m in model_list if "qwen" in str(m).lower()]
                    llama_models = [m for m in model_list if "llama" in str(m).lower()]
                    mistral_models = [m for m in model_list if "mistral" in str(m).lower() or "mixtral" in str(m).lower()]

                    # Select recommended model for directing & reasoning
                    recommended = None
                    if deepseek_models:
                        recommended = deepseek_models[0]
                    elif qwen_models:
                        recommended = qwen_models[0]
                    elif llama_models:
                        recommended = llama_models[0]
                    elif mistral_models:
                        recommended = mistral_models[0]
                    elif model_list:
                        recommended = model_list[0]
                    else:
                        recommended = "deepseek-r1"

                    return {
                        "status": "connected",
                        "endpoint": ep,
                        "latency_ms": latency_ms,
                        "topology": "topology_2_dual_server_internal_llm",
                        "topology_description": (
                            f"Dual-Server Architecture Active: Internal LLM Server detected at {ep} ({recommended}), "
                            f"communicating with ComfyUI Media Engine at {comfy_url}."
                        ),
                        "available_models": model_list[:15],
                        "model_families": {
                            "deepseek": deepseek_models,
                            "qwen": qwen_models,
                            "llama": llama_models,
                            "mistral": mistral_models,
                        },
                        "deepseek_models": deepseek_models,
                        "recommended_model": recommended,
                        "message": f"Successfully connected to internal LLM server at {ep} ({latency_ms} ms).",
                    }
            except (httpx.HTTPError, OSError):
                continue

    return {
        "status": "offline",
        "endpoint": base_url or os.getenv("INTERNAL_LLM_URL", os.getenv("DEEPSEEK_BASE_URL", DEFAULT_ENDPOINTS[0])),
        "topology": "topology_1_single_server_external_llm",
        "topology_description": (
            "Single-Server Architecture Active: Agent LLM operates via external / subscription IDE API "
            "(Cursor, Codex, Kimi Code, Claude Code, Trae). The single GPU (RTX 4090/3090) is 100% "
            f"dedicated to ComfyUI at {comfy_url} (LTX, FLUX, Qwen Vision CV, Higgs TTS) with zero VRAM competition."
        ),
        "message": (
            "No local LLM endpoint found on standard ports (11434, 8000, 8080). "
            "Running in standard Topology 1 (External Agent LLM + ComfyUI GPU Server)."
        ),
        "quick_start_internal_cluster": (
            "To switch to Topology 2 (Internal On-Premise LLM Server), run 'ollama run deepseek-r1:32b' "
            "(or Qwen 2.5 / Llama 3) on the LLM server and export INTERNAL_LLM_URL=http://<llm-server>:11434/v1."
        ),
    }
