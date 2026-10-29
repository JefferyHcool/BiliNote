import csv
import io
import shutil
import subprocess


CUDA_MIN_FREE_MEMORY_RATIO = 0.5


def is_cuda_available() -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False
def is_torch_installed() -> bool:
    try:
        import torch
        return True
    except ImportError:
        return False


def get_cuda_device_with_memory_headroom():
    nvidia_smi = shutil.which("nvidia-smi")
    if not nvidia_smi:
        return None

    try:
        result = subprocess.run(
            [
                nvidia_smi,
                "--query-gpu=index,memory.free,memory.total,name",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            check=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    candidates = []
    for row in csv.reader(io.StringIO(result.stdout), skipinitialspace=True):
        if len(row) != 4:
            continue
        try:
            device_index, free_mib, total_mib = map(int, row[:3])
        except ValueError:
            continue

        if total_mib <= 0:
            continue

        free_ratio = free_mib / total_mib
        if free_ratio > CUDA_MIN_FREE_MEMORY_RATIO:
            candidates.append({
                "index": device_index,
                "name": row[3].strip(),
                "free_memory_bytes": free_mib * 1024 * 1024,
                "total_memory_bytes": total_mib * 1024 * 1024,
                "free_memory_ratio": free_ratio,
            })

    if not candidates:
        return None

    return max(
        candidates,
        key=lambda candidate: (candidate["free_memory_ratio"], candidate["free_memory_bytes"]),
    )
