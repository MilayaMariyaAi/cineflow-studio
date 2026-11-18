"""Hardware profiling, GPU detection, and VRAM profile recommendation."""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class HardwareProfile:
    os_name: str
    platform_name: str
    cpu_cores: int
    ram_gb: float
    disk_free_gb: float
    gpu_name: str | None
    vram_gb: float
    is_cuda: bool
    is_apple_silicon: bool
    recommended_profile: str
    profile_description: str
    recommended_flags: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "os": self.os_name,
            "platform": self.platform_name,
            "cpu_cores": self.cpu_cores,
            "ram_gb": round(self.ram_gb, 1),
            "disk_free_gb": round(self.disk_free_gb, 1),
            "gpu_name": self.gpu_name or "None detected",
            "vram_gb": round(self.vram_gb, 1),
            "is_cuda": self.is_cuda,
            "is_apple_silicon": self.is_apple_silicon,
            "recommended_profile": self.recommended_profile,
            "profile_description": self.profile_description,
            "recommended_flags": self.recommended_flags,
        }


def detect_system_ram_gb() -> float:
    """Returns total system RAM in GB."""
    try:
        if sys.platform == "darwin":
            out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip()
            return int(out) / (1024**3)
        elif sys.platform == "linux":
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        kb = int(line.split()[1])
                        return kb / (1024**2)
        elif sys.platform == "win32":
            out = subprocess.check_output(["wmic", "computersystem", "get", "totalphysicalmemory"], text=True)
            for line in out.splitlines():
                if line.strip().isdigit():
                    return int(line.strip()) / (1024**3)
    except (subprocess.SubprocessError, OSError, ValueError):
        pass
    return 16.0  # safe fallback


def detect_gpu_info() -> tuple[str | None, float, bool, bool]:
    """Detects GPU name, total VRAM (GB), is_cuda flag, is_apple_silicon flag."""
    is_apple = sys.platform == "darwin" and platform.machine() in ("arm64", "aarch64")

    # 1. Try PyTorch CUDA if installed
    try:
        import torch
        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            mem_bytes = torch.cuda.get_device_properties(0).total_memory
            return name, mem_bytes / (1024**3), True, False
        if is_apple and hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            # Apple unified memory
            ram = detect_system_ram_gb()
            return f"Apple Silicon ({platform.processor() or 'M-Series'})", ram, False, True
    except (ImportError, AttributeError, RuntimeError, OSError):
        pass

    # 2. Try nvidia-smi CLI
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            text=True,
            timeout=3,
        ).strip()
        if out:
            line = out.splitlines()[0]
            parts = line.split(",")
            if len(parts) >= 2:
                gpu_name = parts[0].strip()
                vram_mb = float(parts[1].strip())
                return gpu_name, vram_mb / 1024.0, True, False
    except (subprocess.SubprocessError, OSError, ValueError, IndexError):
        pass

    if is_apple:
        ram = detect_system_ram_gb()
        return "Apple Silicon (Unified Memory)", ram, False, True

    return None, 0.0, False, False


def inspect_hardware(target_dir: Path | None = None) -> HardwareProfile:
    """Inspects machine hardware and selects the optimal CineFlow VRAM profile."""
    target_path = Path(target_dir or os.getcwd())
    try:
        disk_usage = shutil.disk_usage(target_path)
        disk_free_gb = disk_usage.free / (1024**3)
    except (OSError, ValueError):
        disk_free_gb = 50.0

    ram_gb = detect_system_ram_gb()
    cpu_cores = os.cpu_count() or 4
    gpu_name, vram_gb, is_cuda, is_apple_silicon = detect_gpu_info()

    # Determine recommended profile
    if is_cuda and vram_gb >= 30.0:
        # Blackwell 32GB class (RTX 5090 etc.): the 4090 bundle plus headroom;
        # portable Comfy needs the cu128 PyTorch build on this architecture.
        recommended_profile = "rtx_5090"
        profile_desc = (
            f"Studio Blackwell 32GB Profile ({gpu_name}, {vram_gb:.1f} GB VRAM). "
            "The full flagship bundle plus headroom for the 9B tier; ComfyUI portable "
            "must run the cu128 PyTorch build (Blackwell needs it)."
        )
        flags = "--highvram --fast --listen 127.0.0.1 --port 8188"
    elif is_cuda and vram_gb >= 22.0:
        # 24GB class unified (#763/#765): a 3090 is the same 24GB card as the
        # 4090 — it gets the flagship bundle (Ampere runs FP8 weights via
        # Comfy's scaled-weights support, just slower than Ada-native).
        recommended_profile = "rtx_4090" if "4090" in (gpu_name or "").lower() else "rtx_3090"
        profile_desc = (
            f"Studio Flagship 24GB Profile ({gpu_name}, {vram_gb:.1f} GB VRAM). "
            "Full-scale single-GPU package: LTX-Video 2.5 FP8, FLUX Klein, Qwen-Image-Edit, "
            "MiniMax H3, Qwen 3.8/2.5-VL Vision (CV), and Higgs v3 TTS inside ComfyUI. "
            "On Ampere (3090) FP8 weights run via scaled-weights support."
        )
        flags = "--highvram --fast --listen 127.0.0.1 --port 8188"
    elif is_cuda and vram_gb >= 14.0:
        recommended_profile = "rtx_16gb"
        profile_desc = (
            f"Optimized 16GB Profile ({gpu_name}, {vram_gb:.1f} GB VRAM). "
            "Uses FP8 quantized weights and sequential model swapping for LTX 2.5 and Qwen 2.1."
        )
        flags = "--fp8_e4m3fn-unet --normalvram --listen 127.0.0.1 --port 8188"
    elif is_cuda and vram_gb >= 8.0:
        recommended_profile = "rtx_12gb"
        profile_desc = (
            f"Lite 12GB Profile ({gpu_name}, {vram_gb:.1f} GB VRAM). "
            "Runs quantized Qwen Image 2.1 and LTX 2.3 locally with CPU offload; video renders fallback to Cloud FastPass."
        )
        flags = "--lowvram --disable-xformers --listen 127.0.0.1 --port 8188"
    elif is_apple_silicon:
        recommended_profile = "apple_silicon"
        profile_desc = (
            f"Apple Silicon Unified Profile ({gpu_name}, {ram_gb:.1f} GB Unified RAM). "
            "Local audio, Higgs TTS, and lightweight image generation; heavy video renders routed to Cloud FastPass."
        )
        flags = "--listen 127.0.0.1 --port 8188"
    else:
        recommended_profile = "cloud_only"
        profile_desc = "No dedicated high-performance GPU detected. Recommended to run via CineFlow Cloud FastPass or external API."
        flags = ""

    return HardwareProfile(
        os_name=platform.system(),
        platform_name=f"{platform.system()} {platform.machine()}",
        cpu_cores=cpu_cores,
        ram_gb=ram_gb,
        disk_free_gb=disk_free_gb,
        gpu_name=gpu_name,
        vram_gb=vram_gb,
        is_cuda=is_cuda,
        is_apple_silicon=is_apple_silicon,
        recommended_profile=recommended_profile,
        profile_description=profile_desc,
        recommended_flags=flags,
    )
