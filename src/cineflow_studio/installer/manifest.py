"""Models and weights manifest for ComfyUI auto-provisioning.

Every entry is verified against its public source (Studio 0b, ticket #678):
`scripts/verify_manifest_urls.py` HEAD-checks each HuggingFace file and
`git ls-remote`-checks each node repo. Entries with no public source are
marked `status="internal"` (weights live on CineFlow infra, not in the
public installer) and are excluded from profile downloads.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ModelWeight:
    name: str
    category: str  # checkpoints, unet, diffusion_models, loras, clip, vae, tts
    hf_repo: str
    hf_filename: str
    local_relative_path: str
    size_gb: float
    required_profiles: list[str]
    description: str
    status: str = "verified"  # verified | internal

    def get_url(self, mirror: str = "huggingface") -> str:
        """Returns direct download URL based on chosen mirror (huggingface, hf-mirror, modelscope)."""
        if mirror == "hf-mirror":
            return f"https://hf-mirror.com/{self.hf_repo}/resolve/main/{self.hf_filename}"
        elif mirror == "modelscope":
            return f"https://modelscope.cn/models/{self.hf_repo}/resolve/master/{self.hf_filename}"
        return f"https://huggingface.co/{self.hf_repo}/resolve/main/{self.hf_filename}"

    def to_dict(self, mirror: str = "huggingface") -> dict[str, str]:
        download_url = self.get_url(mirror)
        return {
            "name": self.name,
            "status": self.status,
            "category": self.category,
            "hf_repo": self.hf_repo,
            "hf_filename": self.hf_filename,
            "local_path": self.local_relative_path,
            "size_gb": f"{self.size_gb:.1f} GB",
            "download_url": download_url,
            "mirror_hf_mirror": self.get_url("hf-mirror"),
            "curl_command": f"curl -L -C - -o '{self.local_relative_path}' '{download_url}'",
            "description": self.description,
        }


# Canonical model inventory. Sizes are the actual HTTP Content-Length of the
# files (verified 2026-11-15 together with the URLs).
MODELS_CATALOG: list[ModelWeight] = [
    ModelWeight(
        name="LTX-Video 2.5 (2B Diffusion)",
        category="checkpoints",
        hf_repo="Lightricks/LTX-Video",
        hf_filename="ltx-video-2b-v0.9.5.safetensors",
        local_relative_path="models/checkpoints/ltx-video-2b-v0.9.5.safetensors",
        size_gb=5.8,
<<<<<<< HEAD
        required_profiles=["rtx_4090", "rtx_5090", "rtx_24gb", "rtx_3090", "rtx_16gb", "rtx_12gb"],
=======
        required_profiles=["rtx_4090", "rtx_24gb", "rtx_3090", "rtx_16gb", "rtx_12gb"],
>>>>>>> b60fec0c0a252aa47937ee8ba510cb7b695760cc
        description="High-speed camera motion and photo-animate video engine (25 fps, 1080p).",
    ),
    ModelWeight(
        name="LTX-Video 2.5 Light (GGUF Q4_K_M)",
        category="checkpoints",
        hf_repo="city96/LTX-Video-gguf",
        hf_filename="ltx-video-2b-v0.9-Q4_K_M.gguf",
        local_relative_path="models/checkpoints/ltx-video-2b-v0.9-Q4_K_M.gguf",
        size_gb=1.4,
        required_profiles=["rtx_3090"],
        description="Lightweight quantized LTX-Video for smooth rendering on RTX 3090 without memory bottlenecks.",
    ),
    ModelWeight(
        name="FLUX.2 Klein 4B (UNET)",
        category="unet",
        hf_repo="Comfy-Org/Flux-2-Klein-4B",
        hf_filename="split_files/diffusion_models/flux-2-klein-4b.safetensors",
        local_relative_path="models/unet/flux-2-klein-4b.safetensors",
        size_gb=7.8,
<<<<<<< HEAD
        required_profiles=["rtx_4090", "rtx_5090", "rtx_24gb", "rtx_3090", "rtx_16gb"],
=======
        required_profiles=["rtx_4090", "rtx_24gb", "rtx_3090", "rtx_16gb"],
>>>>>>> b60fec0c0a252aa47937ee8ba510cb7b695760cc
        description="Core first-frame character turnaround and location panorama synthesizer (FLUX.2 Klein 4B, ComfyUI split package).",
    ),
    ModelWeight(
        name="FLUX.2 Klein Text Encoder (Qwen3-4B)",
        category="clip",
        hf_repo="Comfy-Org/Flux-2-Klein-4B",
        hf_filename="split_files/text_encoders/qwen_3_4b.safetensors",
        local_relative_path="models/text_encoders/qwen_3_4b.safetensors",
        size_gb=8.0,
<<<<<<< HEAD
        required_profiles=["rtx_4090", "rtx_5090", "rtx_24gb", "rtx_3090", "rtx_16gb"],
=======
        required_profiles=["rtx_4090", "rtx_24gb", "rtx_3090", "rtx_16gb"],
>>>>>>> b60fec0c0a252aa47937ee8ba510cb7b695760cc
        description="Qwen3-4B text conditioning for FLUX.2 Klein (replaces T5xxl for FLUX.2 models).",
    ),
    ModelWeight(
        name="FLUX.2 VAE",
        category="vae",
        hf_repo="Comfy-Org/Flux-2-Klein-4B",
        hf_filename="split_files/vae/flux2-vae.safetensors",
        local_relative_path="models/vae/flux2-vae.safetensors",
        size_gb=0.3,
<<<<<<< HEAD
        required_profiles=["rtx_4090", "rtx_5090", "rtx_24gb", "rtx_3090", "rtx_16gb"],
=======
        required_profiles=["rtx_4090", "rtx_24gb", "rtx_3090", "rtx_16gb"],
>>>>>>> b60fec0c0a252aa47937ee8ba510cb7b695760cc
        description="FLUX.2 VAE decoder for Klein image pipelines.",
    ),
    ModelWeight(
        name="FLUX.1 Schnell Light (GGUF Q4_K_S)",
        category="unet",
        hf_repo="city96/FLUX.1-schnell-gguf",
        hf_filename="flux1-schnell-Q4_K_S.gguf",
        local_relative_path="models/unet/flux1-schnell-Q4_K_S.gguf",
        size_gb=6.8,
        required_profiles=["rtx_3090"],
        description="Ultra-fast lightweight FLUX.1 character and location generation for RTX 3090.",
    ),
    ModelWeight(
        name="Qwen-Image-Edit 2509 (FP8)",
        category="diffusion_models",
        hf_repo="Comfy-Org/Qwen-Image-Edit",
        hf_filename="split_files/diffusion_models/qwen_image_edit_2509_fp8_e4m3fn.safetensors",
        local_relative_path="models/diffusion_models/qwen_image_edit_2509_fp8_e4m3fn.safetensors",
        size_gb=19.4,
<<<<<<< HEAD
        required_profiles=["rtx_4090", "rtx_5090", "rtx_24gb", "rtx_3090"],
=======
        required_profiles=["rtx_4090", "rtx_24gb", "rtx_3090"],
>>>>>>> b60fec0c0a252aa47937ee8ba510cb7b695760cc
        description="Last-frame continuity and visual editing model for shot-to-shot transitions.",
    ),
    ModelWeight(
        name="Qwen3-VL 4B Vision (GGUF Q4_K_M)",
        category="unet",
        hf_repo="Qwen/Qwen3-VL-4B-Instruct-GGUF",
        hf_filename="Qwen3VL-4B-Instruct-Q4_K_M.gguf",
        local_relative_path="models/unet/Qwen3VL-4B-Instruct-Q4_K_M.gguf",
        size_gb=2.5,
        required_profiles=["rtx_4090", "rtx_5090", "rtx_24gb", "rtx_3090", "rtx_16gb"],
        description="Vision model for frame inspection, defect detection, and lip-sync closed-mouth validation.",
    ),
    ModelWeight(
        name="T5xxl Text Encoder (FP8)",
        category="clip",
        hf_repo="comfyanonymous/flux_text_encoders",
        hf_filename="t5xxl_fp8_e4m3fn.safetensors",
        local_relative_path="models/clip/t5xxl_fp8_e4m3fn.safetensors",
        size_gb=4.8,
        required_profiles=["rtx_4090", "rtx_5090", "rtx_3090", "rtx_24gb", "rtx_16gb", "rtx_12gb"],
        description="High-capacity text conditioning encoder for LTX-Video cinematic prompt comprehension.",
    ),
    ModelWeight(
        name="Higgs TTS 3 (4B)",
        category="tts",
        hf_repo="bosonai/higgs-tts-3-4b",
        hf_filename="model.safetensors",
        local_relative_path="models/tts/higgs_tts_3_4b.safetensors",
        size_gb=9.3,
        required_profiles=["rtx_4090", "rtx_5090", "rtx_24gb", "rtx_3090", "rtx_16gb"],
        description="Voice synthesis with emotional control and reference voice cloning (Higgs TTS v3, 4B).",
    ),
    ModelWeight(
        name="MiniMax H3 ref2va (FP8 pruned)",
        category="diffusion_models",
        hf_repo="Comfy-Org/MiniMax-H3",
        hf_filename="diffusion_models/minimax_h3_ref2va_pruned_fp8_scaled.safetensors",
        local_relative_path="models/diffusion_models/minimax_h3_ref2va_pruned_fp8_scaled.safetensors",
        size_gb=19.5,
<<<<<<< HEAD
        required_profiles=["rtx_4090", "rtx_5090", "rtx_24gb", "rtx_3090"],
=======
        required_profiles=["rtx_4090", "rtx_24gb", "rtx_3090"],
>>>>>>> b60fec0c0a252aa47937ee8ba510cb7b695760cc
        description="Reference-to-video scene engine: shot frames from the project's reference images (MiniMax H3, ComfyUI package).",
    ),
]


# Custom nodes git repositories. Each url is checked with `git ls-remote`
# by scripts/verify_manifest_urls.py.
CUSTOM_NODES_CATALOG = [
    {
        "name": "ComfyUI-Manager",
        "status": "verified",
        "git_url": "https://github.com/ltdrdata/ComfyUI-Manager.git",
        "description": "Essential package manager for custom nodes and model tracking.",
    },
    {
        "name": "ComfyUI-GGUF",
        "status": "verified",
        "git_url": "https://github.com/city96/ComfyUI-GGUF.git",
        "description": "Enables loading and inference of GGUF-quantized models (FLUX, LTX) on RTX 3090.",
    },
    {
        "name": "ComfyUI_Simple_Qwen3-VL-gguf",
        "status": "verified",
        "git_url": "https://github.com/KLL535/ComfyUI_Simple_Qwen3-VL-gguf.git",
        "description": "Loads GGUF Qwen3-VL vision models for frame inspection and defect scoring.",
    },
    {
        "name": "ComfyUI-QwenVL",
        "status": "verified",
        "git_url": "https://github.com/1038lab/ComfyUI-QwenVL.git",
        "description": "General Qwen VL vision nodes (transformers backend) for captioning and editing tasks.",
    },
    {
        "name": "ComfyUI-LTXVideo",
        "status": "verified",
        "git_url": "https://github.com/Lightricks/ComfyUI-LTXVideo.git",
        "description": "Official custom nodes for LTX-Video i2v and flf2v rendering.",
    },
    {
        "name": "ComfyUI_MiniMaxH3_Director",
        "status": "verified",
        "git_url": "https://github.com/AIMixer/ComfyUI_MiniMaxH3_Director.git",
        "description": "Custom node integration for MiniMax H3 reference-to-video scenes.",
    },
    {
        "name": "Higgs_v3-TTS-ComfyUI",
        "status": "verified",
        "git_url": "https://github.com/Saganaki22/Higgs_v3-TTS-ComfyUI.git",
        "description": "ComfyUI nodes for Higgs TTS v3 audio synthesis and voice cloning.",
    },
    {
        "name": "ComfyUI-VideoHelperSuite",
        "status": "verified",
        "git_url": "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git",
        "description": "Video load, frame combine, and MP4/H.264 export pipeline nodes.",
    },
    {
        "name": "ComfyUI-Advanced-ControlNet",
        "status": "verified",
        "git_url": "https://github.com/Kosinkadink/ComfyUI-Advanced-ControlNet.git",
        "description": "Multi-frame pose, depth, and spatial control for character continuity.",
    },
]


# Verified ComfyUI workflow blueprints for studio pipelines
WORKFLOWS_CATALOG = [
    {
        "id": "ltx_video_img2vid",
        "name": "LTX-Video 2.5 Photo-to-Video Engine",
        "description": "5-second cinematic video synthesis from starting photo and camera motion prompt (25fps, 1080p).",
        "required_nodes": ["ComfyUI-LTXVideo", "ComfyUI-VideoHelperSuite"],
        "required_models": ["LTX-Video 2.5 (2B Diffusion)", "T5xxl Text Encoder (FP8)"],
        "recommended_profile": "rtx_24gb",
        "api_graph": {
            "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "ltx-video-2b-v0.9.5.safetensors"}},
            "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "cinematic camera motion, smooth pan", "clip": ["1", 1]}},
            "3": {"class_type": "LTXVConditioning", "inputs": {"positive": ["2", 0], "frame_rate": 25}},
            "4": {"class_type": "KSampler", "inputs": {"seed": 42, "steps": 30, "cfg": 3.0, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0, "model": ["1", 0], "positive": ["3", 0], "negative": ["8", 0], "latent_image": ["5", 0]}},
            "8": {"class_type": "CLIPTextEncode", "inputs": {"text": "blurry, low quality, distorted faces, watermark", "clip": ["1", 1]}},
            "5": {"class_type": "EmptyLTXVLatentVideo", "inputs": {"width": 1080, "height": 1920, "length": 125, "batch_size": 1}},
            "6": {"class_type": "VAEDecode", "inputs": {"samples": ["4", 0], "vae": ["1", 2]}},
            "7": {"class_type": "VHS_VideoCombine", "inputs": {"images": ["6", 0], "frame_rate": 25, "format": "video/h264-mp4"}},
        },
    },
    {
        "id": "flux_character_turnaround",
        "name": "FLUX.2 Klein Character Turnaround Sheet",
        "description": "Generates 3 consistent angles (front, three-quarters, side profile) for cast identification cards.",
        "required_nodes": ["ComfyUI-Manager"],
        "required_models": [
            "FLUX.2 Klein 4B (UNET)",
            "FLUX.2 Klein Text Encoder (Qwen3-4B)",
            "FLUX.2 VAE",
        ],
        "recommended_profile": "rtx_24gb",
        "api_graph": {
            "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "flux-2-klein-4b.safetensors", "weight_dtype": "default"}},
            "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "model sheet, front view, 3/4 view, side view, neutral lighting", "clip": ["3", 0]}},
            "3": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_3_4b.safetensors", "type": "flux2"}},
            "4": {"class_type": "KSampler", "inputs": {"seed": 101, "steps": 25, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0, "model": ["1", 0], "positive": ["2", 0], "negative": ["9", 0], "latent_image": ["5", 0]}},
            "9": {"class_type": "CLIPTextEncode", "inputs": {"text": "blurry, low quality, distorted faces, watermark", "clip": ["3", 0]}},
            "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 1344, "height": 768, "batch_size": 1}},
            "6": {"class_type": "VAEDecode", "inputs": {"samples": ["4", 0], "vae": ["7", 0]}},
            "7": {"class_type": "VAELoader", "inputs": {"vae_name": "flux2-vae.safetensors"}},
            "8": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": "turnaround"}},
        },
    },
    {
        "id": "higgs_voice_clone_tts",
        "name": "Higgs TTS v3 Speech Synthesis & Voice Cloning",
        "description": "Synthesizes expressive dialogue audio lines with reference voice cloning and emotional tags.",
        "required_nodes": ["Higgs_v3-TTS-ComfyUI"],
        "required_models": ["Higgs TTS 3 (4B)"],
        "recommended_profile": "rtx_24gb",
        "api_graph": {
            "1": {"class_type": "DownloadAndLoadHiggsModel", "inputs": {"model": "higgs_tts_3_4b.safetensors"}},
            "2": {"class_type": "HiggsTTSNode", "inputs": {"model": ["1", 0], "text": "We have only twenty seconds before the security protocol locks the vault.", "emotion": "dramatic_whisper", "speed": 1.0}},
            "3": {"class_type": "SaveAudio", "inputs": {"audio": ["2", 0], "filename_prefix": "dialogue_line"}},
        },
    },
    {
        "id": "qwen_vision_frame_inspect",
        "name": "Qwen3-VL Vision Frame Evaluator & Defect Detector",
        "description": "Embedded ComfyUI CV node: evaluates cinematic quality, detects defects, validates closed-mouth lip-sync guard, and generates visual descriptions (class names per the KLL535 node docs).",
        "required_nodes": ["ComfyUI_Simple_Qwen3-VL-gguf"],
        "required_models": ["Qwen3-VL 4B Vision (GGUF Q4_K_M)"],
        "recommended_profile": "rtx_4090",
        "api_graph": {
            "1": {"class_type": "LoadImage", "inputs": {"image": "keyframe.png"}},
            "2": {"class_type": "Simple_qwen3vl_loader", "inputs": {"gguf_name": "Qwen3VL-4B-Instruct-Q4_K_M.gguf"}},
            "3": {"class_type": "Simple_qwen3vl_generate", "inputs": {
                "model": ["2", 0],
                "image": ["1", 0],
                "prompt": "Inspect this film frame: cinematic quality, artifacts, and whether on-screen speakers have their mouth closed.",
            }},
            "4": {"class_type": "SaveImage", "inputs": {"images": ["3", 0], "filename_prefix": "frame_eval"}},
        },
    },
    {
        "id": "ltx_video_img2vid_3090",
        "name": "LTX-Video 2.5 Light (RTX 3090 GGUF Profile)",
        "description": "Lightweight GGUF-quantized video generation optimized for 24GB RTX 3090 without memory thrashing.",
        "required_nodes": ["ComfyUI-LTXVideo", "ComfyUI-GGUF", "ComfyUI-VideoHelperSuite"],
        "required_models": ["LTX-Video 2.5 Light (GGUF Q4_K_M)", "T5xxl Text Encoder (FP8)"],
        "recommended_profile": "rtx_3090",
        "api_graph": {
            "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "ltx-video-2b-v0.9-Q4_K_M.gguf"}},
            "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "cinematic camera motion, smooth pan", "clip": ["3", 0]}},
            "3": {"class_type": "CLIPLoader", "inputs": {"clip_name": "t5xxl_fp8_e4m3fn.safetensors", "type": "flux"}},
            "4": {"class_type": "KSampler", "inputs": {"seed": 42, "steps": 25, "cfg": 3.0, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0, "model": ["1", 0], "positive": ["2", 0], "negative": ["9", 0], "latent_image": ["5", 0]}},
            "9": {"class_type": "CLIPTextEncode", "inputs": {"text": "blurry, low quality, distorted faces, watermark", "clip": ["3", 0]}},
            "5": {"class_type": "EmptyLTXVLatentVideo", "inputs": {"width": 1080, "height": 1920, "length": 125, "batch_size": 1}},
            "6": {"class_type": "VAEDecode", "inputs": {"samples": ["4", 0], "vae": ["7", 0]}},
            "7": {"class_type": "VAELoader", "inputs": {"vae_name": "ae.safetensors"}},
            "8": {"class_type": "VHS_VideoCombine", "inputs": {"images": ["6", 0], "frame_rate": 25, "format": "video/h264-mp4"}},
        },
    },
]


def get_workflow_template(workflow_id: str) -> dict[str, Any] | None:
    """Finds and returns a workflow blueprint by its identifier."""
    for wf in WORKFLOWS_CATALOG:
        if wf["id"] == workflow_id:
            return wf
    return None


def get_weights_for_profile(profile: str) -> list[ModelWeight]:
    """Returns the subset of verified models required for a specific VRAM hardware profile."""
    return [
        m
        for m in MODELS_CATALOG
        if profile in m.required_profiles and m.status == "verified"
    ]


def calculate_profile_download_size_gb(profile: str) -> float:
    weights = get_weights_for_profile(profile)
    return round(sum(w.size_gb for w in weights), 1)
