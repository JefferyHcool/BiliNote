#!/usr/bin/env bash
set -euo pipefail

backend_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(dirname "$backend_dir")"
python_bin="${BILINOTE_PYTHON:-$(command -v python3)}"

if [[ -z "${BILINOTE_PYTHON:-}" && -x "$project_root/.venv/bin/python" ]]; then
    python_bin="$project_root/.venv/bin/python"
fi

site_packages="$("$python_bin" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
cuda_library_path=""
for library_dir in "$site_packages"/nvidia/*/lib; do
    [[ -d "$library_dir" ]] || continue
    cuda_library_path="${cuda_library_path:+${cuda_library_path}:}${library_dir}"
done

if [[ -n "$cuda_library_path" ]]; then
    export LD_LIBRARY_PATH="${cuda_library_path}${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
fi

cd "$backend_dir"
exec "$python_bin" main.py
