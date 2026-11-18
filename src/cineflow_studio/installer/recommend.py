"""Hardware recommendations for the IDE agent (Hybrid #765).

The agent is the onboarding engineer: it inspects the machine, gets here the
verified bundle for the detected profile, the workflows that profile runs,
the ComfyUI launch flags — and a set of ready web-search queries so it can
research NEWER models online before proposing an install to the user.

Rules the agent must follow (SKILL.md hardware protocol):
- the manifest is the VERIFIED base (every source was checked, ticket #678);
- web findings are PROPOSALS to the user, never a silent install;
- any URL proposed from the web gets a HEAD check first, and gated repos
  (401, e.g. black-forest-labs 9B) are marked as needing an HF login;
- nothing downloads without the user's yes.
"""
from __future__ import annotations

from typing import Any

from cineflow_studio.installer.manifest import get_weights_for_profile

# Verified-base notes per profile: what the web research should check first.
_PROFILE_NOTES: dict[str, list[str]] = {
    "rtx_5090": [
        "Blackwell (sm_120): ComfyUI portable must ship the cu128 PyTorch build.",
        "The 9B Klein UNET is a gated BFL repo (HF login) — mark it as advanced.",
        "32GB headroom: the 4090 bundle fits with room for larger UNETs.",
    ],
    "rtx_4090": [
        "Ada-native FP8 acceleration: prefer FP8 weights over GGUF where both exist.",
        "24GB fits every engine in the bundle; MiniMax H3 (19.5GB fp8) is the heaviest.",
    ],
    "rtx_3090_full": [
        "Ampere: FP8 weights run via Comfy scaled-weights support (slower than Ada-native).",
        "The registry_3090 workflows reference the 9B fp8 UNET (gated BFL repo, HF login).",
        "LTX Light Q4 is the fast fallback when VRAM gets tight.",
    ],
    "rtx_16gb": [
        "FP8 quantized weights + sequential swapping; MiniMax H3 and the 9B tier do not fit.",
    ],
    "rtx_12gb": [
        "Quantized Qwen Image 2.1 + LTX with CPU offload; video renders should fall back to cloud.",
    ],
    "apple_silicon": [
        "Local audio/TTS and light image only; heavy video renders route to cloud.",
    ],
    "cloud_only": [
        "No local generation: everything routes to the CineFlow cloud.",
    ],
}

_RESEARCH_QUERIES = [
    "ComfyUI {topic} workflow best practices latest",
    "huggingface {topic} fp8 safetensors Comfy-Org 2026",
    "{gpu} ComfyUI optimization flags 2026",
]


def recommend_bundle(profile: str, gpu_name: str | None = None) -> dict[str, Any]:
    """The verified bundle, workflows and research hints for one hardware
    profile — everything the agent needs to propose an install."""
    weights = get_weights_for_profile(profile)
    bundle = [
        {
            "name": w.name,
            "size_gb": w.size_gb,
            "source": f"{w.hf_repo}/{w.hf_filename}",
            "install_path": w.local_relative_path,
            "required_profiles": list(w.required_profiles),
        }
        for w in sorted(weights, key=lambda m: -m.size_gb)
    ]
    gpu = gpu_name or profile
    research = [
        q.replace("{topic}", topic).replace("{gpu}", gpu)
        for topic in ("image edit model", "reference-to-video model", "TTS voice clone model")
        for q in _RESEARCH_QUERIES[:2]
    ][:6]
    return {
        "profile": profile,
        "bundle": bundle,
        "total_gb": round(sum(w.size_gb for w in weights), 1),
        "notes": _PROFILE_NOTES.get(profile, ["Unknown profile: verify before proposing."]),
        "research_queries": research,
        "rules": [
            "The manifest is the verified base; web findings are PROPOSALS to the user.",
            "HEAD-check every web URL before proposing; mark gated repos (401) as HF-login required.",
            "Nothing downloads without the user's explicit yes (cineflow_download_model / install bat).",
        ],
    }
