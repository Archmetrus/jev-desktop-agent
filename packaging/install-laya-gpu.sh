#!/usr/bin/env bash
# Run only after the user approves CUDA dependency downloads.
set -euo pipefail
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
export UV_CACHE_DIR="$project_dir/.local/laya/uv-cache"
export UV_PYTHON_DOWNLOADS=never
uv pip install --python "$project_dir/.local/laya/venv/bin/python" --torch-backend auto --reinstall-package torch 'torch==2.14.0'
"$project_dir/.local/laya/venv/bin/python" -c 'import torch; assert torch.cuda.is_available(), "CUDA unavailable"; print(torch.cuda.get_device_name(0))'
uv pip freeze --python "$project_dir/.local/laya/venv/bin/python" > "$project_dir/packaging/laya-requirements.lock"
