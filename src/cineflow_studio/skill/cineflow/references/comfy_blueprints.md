# CineFlow ComfyUI Blueprints & Node Schemes

This reference specifies verified ComfyUI node graphs, model parameters, and execution topologies for CineFlow productions.

---

## 1. Engine Specifications & Parameters

### A. LTX-Video 2.5 (High-Definition Image-to-Video)
- **Model Files:**
  - Standard/FP8: `ltx-video-2b-v0.9.5-fp8.safetensors` (~5.8 GB)
  - Light/GGUF: `ltx-video-2b-v0.9.5-q4_k_m.gguf` (~3.8 GB)
- **Target Subdirectory:** `ComfyUI/models/checkpoints/`
- **Native Resolution:** 768x512, 1280x720 (16:9), or 512x768 (9:16 vertical)
- **Frame Rate:** 24 or 25 fps
- **Recommended Settings:**
  - Steps: `25–30`
  - CFG: `3.0–3.5`
  - Sampler: `euler`
  - Scheduler: `normal`
  - Motion Scale: `0.8–1.2`
- **Node Scheme:**
  `LoadImage` -> `LTXVideoCheckpointLoader` -> `LTXVideoSampler` -> `VAEDecode` -> `SaveAnimatedWEBP` / `SaveVideo`

### B. FLUX.1 / Klein (Character Turnarounds & Keyframes)
- **Model Files:**
  - Standard: `flux1-dev-fp8.safetensors` (~9.4 GB)
  - Light: `flux1-schnell-q4_k_m.gguf` (~5.2 GB)
- **Target Subdirectory:** `ComfyUI/models/unet/` or `checkpoints/`
- **CLIP Models:** `clip_l.safetensors`, `t5xxl_fp8_e4m3fn.safetensors`
- **Recommended Settings:**
  - Schnell Steps: `4–6`, CFG: `1.0`
  - Dev Steps: `20–25`, CFG: `3.5`
  - Sampler: `euler`
  - Scheduler: `simple` / `sgm_uniform`
- **Node Scheme:**
  `DualCLIPLoader` + `UNETLoader` -> `EmptyLatentImage` -> `KSampler` -> `VAEDecode` -> `SaveImage`

### C. Qwen 2.5-VL / Qwen 3.8 Vision (Computer Vision & Quality Audit)
- **Model Files:**
  - FP8: `Qwen2.5-VL-7B-Instruct-FP8` (~7.6 GB)
  - GGUF: `Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf` (~2.4 GB)
- **Target Subdirectory:** `ComfyUI/models/LLM/` or `custom_nodes/ComfyUI-Qwen-VL/`
- **Capabilities:**
  - Aesthetic scoring (1-10)
  - Closed-mouth lip-sync guard verification (Rule D)
  - Artifact detection (anatomy, blur, jitter)
  - Reference auto-captioning in cinematic English
- **Node Scheme:**
  `LoadImage` -> `QwenVLModelLoader` -> `QwenVLChat` -> `ShowText` / `SaveText`

### D. Higgs v3 (Voice Cloning & TTS)
- **Model Files:**
  - Base: `higgs_tts_3_4b.safetensors` (~9.3 GB, `bosonai/higgs-tts-3-4b`)
- **Voice Assets:** the user's own reference WAVs and transcripts (voice cloning works from any local sample; CineFlow's curated voice bank is not distributed with the public installer)
- **Target Subdirectory:** `ComfyUI/models/tts/`
- **Node Scheme:**
  `LoadAudio` (reference voice) + `HiggsTTSLoader` -> `HiggsTTSSynthesizer` -> `SaveAudio`

---

## 2. Dynamic Memory Management & Co-Location

On a single 24GB VRAM GPU (RTX 4090 or RTX 3090):
- Running standalone vLLM + ComfyUI simultaneously triggers CUDA Out-Of-Memory (OOM).
- In CineFlow, **all models run inside ComfyUI's unified execution graph**.
- ComfyUI's dynamic memory manager (`model_management.load_models_gpu`) automatically:
  1. Offloads the diffusion UNet to CPU RAM when running Qwen Vision CV.
  2. Offloads Qwen Vision when swapping to LTX-Video.
  3. Caches VAE decoders across sequential takes.

### ComfyUI Startup Flags by Hardware Profile

| Profile | GPU | Flags |
|---|---|---|
| `rtx_4090` | RTX 4090 (24GB) | `--highvram --fast --disable-xformers` |
| `rtx_3090` | RTX 3090 (24GB) | `--normalvram --lowvram --gpu-only-unet` |
| `apple_silicon` | M-series Mac | `--force-fp16 --directml` |

---

## 3. Workflow Artifact Persistence Protocol

Every execution of a ComfyUI workflow via `cineflow_comfy_workflow_execute` or `cineflow_shot_record_artifact` must persist two paired files:

1. **Workflow Blueprint (`.comfy.json`):**
   - Path: `scenes/{scene_id}/workflows/{shot_id}.comfy.json`
   - Content: Complete JSON node graph, including node IDs, connections, model paths, seeds, and sampler steps.
2. **Passport Sidecar (`.cineflow.json`):**
   - Path: `scenes/{scene_id}/video/{shot_id}.cineflow.json`
   - Content:
     ```json
     {
       "shot_id": "shot_01",
       "project_id": "noir_detective",
       "scene_id": "scene_01",
       "seed": 42819283,
       "model": "ltx-video-2b-v0.9.5-fp8.safetensors",
       "prompt": "Cinematic 35mm, slow dolly-in on <Subject 1>, rain drops glistening on trenchcoat, moody chiaroscuro lighting.",
       "workflow_path": "scenes/scene_01/workflows/shot_01.comfy.json",
       "comfy_url": "http://127.0.0.1:8188",
       "created_at": "2026-11-12T10:00:00Z"
     }
     ```
This enables DaVinci Resolve or any NLE editor to right-click a clip and immediately reopen the exact generation pipeline in ComfyUI.
