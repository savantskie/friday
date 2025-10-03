#!/usr/bin/env python3
"""Lightweight GPU utilities for Linux: detection, usage, and memory.

This module provides a small, robust set of helpers that try nvidia-smi,
rocm-smi, and lspci to detect GPUs and to report simple utilization and
memory statistics. It's intentionally conservative and returns safe
defaults when tools aren't available.
"""
from typing import Dict
import subprocess
import shlex


def _run(cmd, timeout=3):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        return ""
    return ""


def detect_gpu_info() -> str:
    # Try nvidia-smi first
    out = _run(['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader,nounits'])
    if out:
        lines = [l.strip() for l in out.splitlines() if l.strip()]
        gpus = []
        for line in lines:
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 2:
                name = parts[0]
                ram = parts[1]
                gpus.append(f"{name} ({ram} MB)")
            else:
                gpus.append(parts[0])
        return ' | '.join(gpus)

    # Try rocm-smi
    out = _run(['rocm-smi', '--showproductname'])
    if out:
        lines = [l.strip() for l in out.splitlines() if l.strip()]
        return ' | '.join(lines)

    # Fallback to lspci
    out = _run(['lspci', '-nn'])
    if out:
        gpus = []
        for line in out.splitlines():
            if 'VGA compatible controller' in line or 'Display controller' in line:
                # trim the PCI id prefix
                parts = line.split(':', 2)
                if len(parts) >= 3:
                    gpus.append(parts[2].strip())
                else:
                    gpus.append(line)
        if gpus:
            return ' | '.join(gpus)

    return 'GPU present but detection unavailable'


def get_gpu_usage() -> Dict:
    """Return a GPU usage dict with keys similar to the GUI expectations.

    For Linux this maps to simple overall/utilization numbers when possible.
    """
    data = {
        "usage_3d": 0.0,
        "usage_compute": 0.0,
        "usage_copy": 0.0,
        "usage_video": 0.0,
        "overall_usage": 0.0
    }

    # NVIDIA: try nvidia-smi for utilization
    out = _run(['nvidia-smi', '--query-gpu=utilization.gpu', '--format=csv,noheader,nounits'])
    if out:
        try:
            # take first GPU if multiple
            first = out.splitlines()[0].strip()
            val = float(first)
            data['usage_compute'] = val
            data['overall_usage'] = val
            return data
        except Exception:
            pass

    # AMD ROCm: try rocm-smi (best-effort parsing)
    out = _run(['rocm-smi', '--showuse'])
    if out:
        # rocm-smi prints something like: GPU[0] Average GPU use:  4 %
        try:
            for line in out.splitlines():
                if 'Average GPU use' in line or 'GPU use' in line:
                    parts = line.split(':')
                    if len(parts) >= 2:
                        val = parts[-1].strip().strip('%').strip()
                        valf = float(val)
                        data['usage_compute'] = valf
                        data['overall_usage'] = valf
                        return data
        except Exception:
            pass

    # Intel: try intel_gpu_top non-interactive output if available (best-effort)
    # As a fallback return zeros
    return data


def get_gpu_memory_usage() -> Dict:
    """Return GPU memory usage in MB using nvidia-smi or rocm-smi when available."""
    memory_data = {
        "dedicated_used_mb": 0,
        "dedicated_total_mb": 0,
        "shared_used_mb": 0,
        "shared_total_mb": 0,
        "usage_percent": 0.0
    }

    # NVIDIA
    out = _run(['nvidia-smi', '--query-gpu=memory.used,memory.total', '--format=csv,noheader,nounits'])
    if out:
        try:
            first = out.splitlines()[0].strip()
            parts = [p.strip() for p in first.split(',')]
            if len(parts) >= 2:
                used = int(float(parts[0]))
                total = int(float(parts[1]))
                memory_data['dedicated_used_mb'] = used
                memory_data['dedicated_total_mb'] = total
                if total > 0:
                    memory_data['usage_percent'] = (used / total) * 100.0
                return memory_data
        except Exception:
            pass

    # AMD ROCm (best-effort): rocm-smi --showmem
    out = _run(['rocm-smi', '--showmem'])
    if out:
        try:
            # Parse lines like: GPU[0] VRAM Usage: 1836 MiB / 24576 MiB (7 %)
            for line in out.splitlines():
                if 'VRAM Usage' in line or 'VRAM' in line:
                    import re
                    m = re.search(r"(\d+)\s*MiB\s*/\s*(\d+)\s*MiB", line)
                    if m:
                        used = int(m.group(1))
                        total = int(m.group(2))
                        memory_data['dedicated_used_mb'] = used
                        memory_data['dedicated_total_mb'] = total
                        if total > 0:
                            memory_data['usage_percent'] = (used / total) * 100.0
                        return memory_data
        except Exception:
            pass

    # Fallback: unknown
    return memory_data
