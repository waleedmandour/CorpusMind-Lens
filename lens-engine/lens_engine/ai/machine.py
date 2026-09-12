"""Machine capability probe — powers model-fit recommendations (v0.2).

Why: pulling a 7B model onto a 8GB-RAM laptop without a GPU is a support
ticket waiting to happen. The Setup screen and the model catalog both ask
this module "what can this machine actually run?" and show honest
fits/it-will-not-fit badges BEFORE a multi-GB download starts.

The desktop shell probes specs natively (Rust, `sysinfo`) and the engine
falls back to this stdlib-only probe in PWA/browser mode where no shell is
present. Both feed the same JSON shape, so the UI has one contract:

    {
      "os": "windows", "os_version": "11", "arch": "x86_64",
      "cpu_cores": 8, "cpu_model": "...",
      "ram_gb": 16.0,
      "gpus": [{"name": "NVIDIA GeForce RTX 3060", "vram_gb": 12.0}],
      "disk_free_gb": 120.4,
      "source": "shell" | "engine"
    }

GPU detection is best-effort and never fatal: NVIDIA via ``nvidia-smi``
(the only vendor CLI guaranteed to report VRAM), macOS unified memory is
reported as a pseudo-GPU (Apple Silicon shares RAM with the GPU), and an
unknown GPU simply means "CPU-fit estimates only".
"""
from __future__ import annotations

import platform
import re
import shutil
import subprocess
from typing import Any

from ..logging import get_logger

log = get_logger(__name__)


def _read_proc_meminfo_gb() -> float | None:
    try:
        txt = open("/proc/meminfo").read()
    except OSError:
        return None
    m = re.search(r"^MemTotal:\s+(\d+)\s*kB", txt, re.MULTILINE)
    return round(int(m.group(1)) / 1024 / 1024, 1) if m else None


def _macos_ram_gb() -> float | None:
    try:
        out = subprocess.run(
            ["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=5
        )
        return round(int(out.stdout.strip()) / 1024**3, 1)
    except Exception:
        return None


def _windows_ram_gb() -> float | None:
    try:
        out = subprocess.run(
            ["wmic", "ComputerSystem", "get", "TotalPhysicalMemory"],
            capture_output=True, text=True, timeout=10,
        )
        val = re.search(r"(\d{9,})", out.stdout)
        return round(int(val.group(1)) / 1024**3, 1) if val else None
    except Exception:
        return None


def _nvidia_gpus() -> list[dict[str, Any]]:
    try:
        exe = shutil.which("nvidia-smi")
        if not exe:
            return []
        out = subprocess.run(
            [exe, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
        gpus = []
        for line in out.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 2:
                gpus.append({"name": parts[0], "vram_gb": round(float(parts[1]) / 1024, 1)})
        return gpus
    except Exception:
        return []


def _macos_gpu_name() -> str | None:
    try:
        out = subprocess.run(
            ["system_profiler", "SPDisplaysDataType"], capture_output=True, text=True, timeout=15
        )
        m = re.search(r"Chipset Model: (.+)", out.stdout)
        return m.group(1).strip() if m else None
    except Exception:
        return None


def _cpu_model() -> str:
    if platform.system() == "Darwin":
        try:
            out = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"],
                                 capture_output=True, text=True, timeout=5)
            return out.stdout.strip() or platform.processor() or "unknown"
        except Exception:
            pass
    return platform.processor() or "unknown"


def probe() -> dict[str, Any]:
    """Best-effort machine specs. Missing values stay missing; nothing raises."""
    system = platform.system()  # Windows | Darwin | Linux
    ram_gb: float | None = None
    if system == "Linux":
        ram_gb = _read_proc_meminfo_gb()
    elif system == "Darwin":
        ram_gb = _macos_ram_gb()
    elif system == "Windows":
        ram_gb = _windows_ram_gb()

    gpus: list[dict[str, Any]] = []
    if system == "Darwin" and (ram_gb is not None):
        # Apple Silicon: unified memory — the GPU can address most of RAM.
        name = _macos_gpu_name() or "Apple GPU (unified memory)"
        gpus.append({"name": name, "vram_gb": round(ram_gb * 0.75, 1), "unified": True})
    else:
        gpus = _nvidia_gpus()

    try:
        from ..config import get_settings

        disk_free_gb = round(shutil.disk_usage(get_settings().data_dir).free / 1024**3, 1)
    except Exception:
        disk_free_gb = None

    return {
        "os": system.lower(),
        "os_version": platform.release(),
        "arch": platform.machine(),
        "cpu_cores": platform.machine() and (__import__("os").cpu_count() or 0),
        "cpu_model": _cpu_model(),
        "ram_gb": ram_gb,
        "gpus": gpus,
        "disk_free_gb": disk_free_gb,
        "source": "engine",
    }
