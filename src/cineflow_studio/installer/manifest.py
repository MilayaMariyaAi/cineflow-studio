"""Models and weights manifest for ComfyUI auto-provisioning."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ModelWeight:
    name: str
    category: str  # checkpoints, unet, loras, clip, vae, tts
    hf_repo: str
    hf_filename: str
    local_relative_path: str
    size_gb: float
    required_profiles: list[str]
    description: str

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


# Canonical model inventory
MODELS_CATALOG: list[ModelWeight] = [
    ModelWeight(
        name="LTX-Video 2.5 (2B Diffusion)",
        category="checkpoints",
        hf_repo="Lightricks/LTX-Video",
        hf_filename="ltx-video-2b-v0.9.5.safetensors",
        local_relative_path="models/checkpoints/ltx-video-2b-v0.9.5.safetensors",
        size_gb=5.8,
        required_profiles=["rtx_4090", "rtx_24gb", "rtx_16gb", "rtx_12gb"],
        description="High-speed camera motion and photo-animate video engine (25 fps, 1080p).",
    ),
    ModelWeight(
        name="LTX-Video 2.5 Light (GGUF Q4_K_M)",
        category="checkpoints",
        hf_repo="city96/LTX-Video-GGUF",
        hf_filename="ltx-video-2b-v0.9.5-q4_k_m.gguf",
        local_relative_path="models/checkpoints/ltx-video-2b-v0.9.5-q4_k_m.gguf",
        size_gb=3.8,
        required_profiles=["rtx_3090"],
        description="Lightweight quantized LTX-Video 2.5 for smooth rendering on RTX 3090 without memory bottlenecks.",
    ),
    ModelWeight(
        name="FLUX 2 Klein 9B (FP8 Quantized)",
        category="unet",
        hf_repo="black-forest-labs/FLUX.1-schnell",
        hf_filename="flux-2-klein-9b-fp8.safetensors",
        local_relative_path="models/unet/flux-2-klein-9b-fp8.safetensors",
        size_gb=9.4,
        required_profiles=["rtx_4090", "rtx_24gb"],
        description="Core first-frame character turnaround and location panorama synthesizer.",
    ),
    ModelWeight(
        name="FLUX.1 Schnell Light (GGUF Q4_K_S)",
        category="unet",
        hf_repo="city96/FLUX.1-schnell-gguf",
        hf_filename="flux1-schnell-q4_k_s.gguf",
        local_relative_path="models/unet/flux1-schnell-q4_k_s.gguf",
        size_gb=5.2,
        required_profiles=["rtx_3090", "rtx_16gb"],
        description="Ultra-fast lightweight FLUX.1 character and location generation for RTX 3090.",
    ),
    ModelWeight(
        name="Qwen Image 2.1 EditUtils",
        category="unet",
        hf_repo="Qwen/Qwen2-VL-7B-Instruct",
        hf_filename="qwen-image-2.1-edit-fp8.safetensors",
        local_relative_path="models/unet/qwen-image-2.1-edit-fp8.safetensors",
        size_gb=8.6,
        required_profiles=["rtx_4090", "rtx_24gb"],
        description="Last-frame continuity and visual editing model for shot-to-shot transitions.",
    ),
    ModelWeight(
        name="Qwen 3.8 / Qwen2.5-VL 7B Vision (FP8)",
        category="unet",
        hf_repo="Qwen/Qwen2.5-VL-7B-Instruct",
        hf_filename="qwen2.5-vl-7b-instruct-fp8.safetensors",
        local_relative_path="models/unet/qwen2.5-vl-7b-instruct-fp8.safetensors",
        size_gb=7.6,
        required_profiles=["rtx_4090", "rtx_24gb"],
        description="Embedded vision & CV model inside ComfyUI for frame inspection, defect detection, and lip-sync closed-mouth validation.",
    ),
    ModelWeight(
        name="Qwen 3.8 / Qwen2.5-VL 3B Vision (GGUF Q4_K_M)",
        category="unet",
        hf_repo="Qwen/Qwen2.5-VL-3B-Instruct-GGUF",
        hf_filename="qwen2.5-vl-3b-instruct-q4_k_m.gguf",
        local_relative_path="models/unet/qwen2.5-vl-3b-instruct-q4_k_m.gguf",
        size_gb=2.4,
        required_profiles=["rtx_3090", "rtx_16gb"],
        description="Lightweight 2.4GB vision model for fast keyframe evaluation and defect checking on RTX 3090.",
    ),
    ModelWeight(
        name="T5xxl Text Encoder (FP8)",
        category="clip",
        hf_repo="comfyanonymous/flux_text_encoders",
        hf_filename="t5xxl_fp8_e4m3fn.safetensors",
        local_relative_path="models/clip/t5xxl_fp8_e4m3fn.safetensors",
        size_gb=4.8,
        required_profiles=["rtx_4090", "rtx_3090", "rtx_24gb", "rtx_16gb", "rtx_12gb"],
        description="High-capacity text conditioning encoder for cinematic prompt comprehension.",
    ),
    ModelWeight(
        name="Higgs v3 TTS Speech Generator",
        category="tts",
        hf_repo="cineflow/higgs-tts-v3",
        hf_filename="higgs_v3_base.safetensors",
        local_relative_path="models/tts/higgs_v3_base.safetensors",
        size_gb=2.1,
        required_profiles=["rtx_4090", "rtx_3090", "rtx_24gb", "rtx_16gb", "rtx_12gb", "apple_silicon"],
        description="Voice synthesis with emotional control and 3-second reference voice cloning.",
    ),
    ModelWeight(
        name="MiniMax H3 Motion LoRA (Turbo)",
        category="loras",
        hf_repo="cineflow/minimax-h3-weights",
        hf_filename="minimax_h3_turbo_lora.safetensors",
        local_relative_path="models/loras/minimax_h3_turbo_lora.safetensors",
        size_gb=1.2,
        required_profiles=["rtx_4090", "rtx_24gb"],
        description="Dynamic multi-character scene motion LoRA with lip-sync stabilization.",
    ),
]


# Custom nodes git repositories
CUSTOM_NODES_CATALOG = [
    {
        "name": "ComfyUI-Manager",
        "git_url": "https://github.com/ltdrdata/ComfyUI-Manager.git",
        "description": "Essential package manager for custom nodes and model tracking.",
    },
    {
        "name": "ComfyUI-GGUF",
        "git_url": "https://github.com/city96/ComfyUI-GGUF.git",
        "description": "Enables loading and inference of GGUF-quantized models (FLUX, LTX, Qwen Vision) on RTX 3090.",
    },
    {
        "name": "ComfyUI-Qwen-VL",
        "git_url": "https://github.com/cineflow/ComfyUI-Qwen-VL.git",
        "description": "Native ComfyUI node for Qwen 3.8 / 2.5-VL Vision inference, frame inspection, and defect scoring.",
    },
    {
        "name": "ComfyUI-LTXVideo",
        "git_url": "https://github.com/Lightricks/ComfyUI-LTXVideo.git",
        "description": "Official custom nodes for LTX-Video 2.5 ia2v and flf2v rendering.",
    },
    {
        "name": "ComfyUI_MiniMax_H3",
        "git_url": "https://github.com/cineflow/ComfyUI_MiniMax_H3.git",
        "description": "Custom node integration for MiniMax H3 reference-to-video scenes.",
    },
    {
        "name": "ComfyUI-Higgs-TTS",
        "git_url": "https://github.com/cineflow/ComfyUI-Higgs-TTS.git",
        "description": "Direct ComfyUI nodes for audio synthesis and voice cloning.",
    },
    {
        "name": "ComfyUI-VideoHelperSuite",
        "git_url": "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git",
        "description": "Video load, frame combine, and MP4/H.264 export pipeline nodes.",
    },
    {
        "name": "ComfyUI-Advanced-ControlNet",
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
            "4": {"class_type": "KSampler", "inputs": {"seed": 42, "steps": 30, "cfg": 3.0, "sampler_name": "euler", "scheduler": "normal", "model": ["1", 0], "positive": ["3", 0], "latent_image": ["5", 0]}},
            "5": {"class_type": "EmptyLTXVLatentVideo", "inputs": {"width": 1080, "height": 1920, "length": 125, "batch_size": 1}},
            "6": {"class_type": "VAEDecode", "inputs": {"samples": ["4", 0], "vae": ["1", 2]}},
            "7": {"class_type": "VHS_VideoCombine", "inputs": {"images": ["6", 0], "frame_rate": 25, "format": "video/h264-mp4"}},
        },
    },
    {
        "id": "flux_character_turnaround",
        "name": "FLUX Klein 9B Character Turnaround Sheet",
        "description": "Generates 3 consistent angles (front, three-quarters, side profile) for cast identification cards.",
        "required_nodes": ["ComfyUI-Manager"],
        "required_models": ["FLUX 2 Klein 9B (FP8 Quantized)", "T5xxl Text Encoder (FP8)"],
        "recommended_profile": "rtx_24gb",
        "api_graph": {
            "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "flux-2-klein-9b-fp8.safetensors", "weight_dtype": "fp8_e4m3fn"}},
            "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "model sheet, front view, 3/4 view, side view, neutral lighting", "clip": ["3", 0]}},
            "3": {"class_type": "CLIPLoader", "inputs": {"clip_name": "t5xxl_fp8_e4m3fn.safetensors", "type": "flux"}},
            "4": {"class_type": "KSampler", "inputs": {"seed": 101, "steps": 25, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "model": ["1", 0], "positive": ["2", 0], "latent_image": ["5", 0]}},
            "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 1344, "height": 768, "batch_size": 1}},
            "6": {"class_type": "VAEDecode", "inputs": {"samples": ["4", 0], "vae": ["7", 0]}},
            "7": {"class_type": "VAELoader", "inputs": {"vae_name": "ae.safetensors"}},
            "8": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": "turnaround"}},
        },
    },
    {
        "id": "higgs_voice_clone_tts",
        "name": "Higgs v3 Speech Synthesis & Voice Cloning",
        "description": "Synthesizes expressive dialogue audio lines with 3-second reference voice cloning and emotional tags.",
        "required_nodes": ["ComfyUI-Higgs-TTS"],
        "required_models": ["Higgs v3 TTS Speech Generator"],
        "recommended_profile": "apple_silicon",
        "api_graph": {
            "1": {"class_type": "HiggsModelLoader", "inputs": {"model_name": "higgs_v3_base.safetensors"}},
            "2": {"class_type": "HiggsTTSNode", "inputs": {"model": ["1", 0], "text": "We have only twenty seconds before the security protocol locks the vault.", "emotion": "dramatic_whisper", "speed": 1.0}},
            "3": {"class_type": "SaveAudio", "inputs": {"audio": ["2", 0], "filename_prefix": "dialogue_line"}},
        },
    },
    {
        "id": "qwen_vision_frame_inspect",
        "name": "Qwen 3.8 Vision Frame Evaluator & Defect Detector",
        "description": "Embedded ComfyUI CV node: evaluates cinematic quality, detects defects, validates closed-mouth lip-sync guard, and generates visual descriptions.",
        "required_nodes": ["ComfyUI-Qwen-VL"],
        "required_models": ["Qwen 3.8 / Qwen2.5-VL 7B Vision (FP8)"],
        "recommended_profile": "rtx_4090",
        "api_graph": {
            "1": {"class_type": "LoadImage", "inputs": {"image": "keyframe.png"}},
            "2": {"class_type": "QwenVLModelLoader", "inputs": {"model_name": "qwen2.5-vl-7b-instruct-fp8.safetensors"}},
            "3": {"class_type": "QwenVLInspectorNode", "inputs": {
                "model": ["2", 0],
                "image": ["1", 0],
                "task": "inspect_cinematic_quality_and_artifacts",
                "check_closed_mouth": True,
            }},
            "4": {"class_type": "SaveInspectionReport", "inputs": {"report": ["3", 0], "filename_prefix": "frame_eval"}},
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
            "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "ltx-video-2b-v0.9.5-q4_k_m.gguf"}},
            "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "cinematic camera motion, smooth pan", "clip": ["3", 0]}},
            "3": {"class_type": "CLIPLoader", "inputs": {"clip_name": "t5xxl_fp8_e4m3fn.safetensors", "type": "flux"}},
            "4": {"class_type": "KSampler", "inputs": {"seed": 42, "steps": 25, "cfg": 3.0, "sampler_name": "euler", "scheduler": "normal", "model": ["1", 0], "positive": ["2", 0], "latent_image": ["5", 0]}},
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
    """Returns the subset of models required for a specific VRAM hardware profile."""
    return [m for m in MODELS_CATALOG if profile in m.required_profiles]


def calculate_profile_download_size_gb(profile: str) -> float:
    weights = get_weights_for_profile(profile)
    return round(sum(w.size_gb for w in weights), 1)
