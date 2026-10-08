#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
  echo "usage: prepare-leaf-rotation-runtime.sh <venv-dir> <worker-script> [wheelhouse]" >&2
  exit 2
fi

runtime_dir=$1
worker_script=$2
wheelhouse=${3:-}

case "$runtime_dir" in
  /*) ;;
  *) echo "runtime directory must be absolute" >&2; exit 2 ;;
esac

if [ ! -f "$worker_script" ] || [ -L "$worker_script" ]; then
  echo "worker script must be a regular non-symlink file" >&2
  exit 2
fi

if [ ! -x "$runtime_dir/bin/python" ]; then
  if [ -e "$runtime_dir" ]; then
    echo "refusing to replace a non-runtime path" >&2
    exit 2
  fi
  python3 -m venv "$runtime_dir"
fi

pip_args=(--disable-pip-version-check --no-input --upgrade 'cryptography==50.0.1')
if [ -n "$wheelhouse" ]; then
  if [ ! -d "$wheelhouse" ] || [ -L "$wheelhouse" ]; then
    echo "wheelhouse must be a regular directory" >&2
    exit 2
  fi
  pip_args=(--disable-pip-version-check --no-input --no-index --find-links "$wheelhouse" --upgrade 'cryptography==50.0.1')
fi

"$runtime_dir/bin/python" -m pip install "${pip_args[@]}" >/dev/null
"$runtime_dir/bin/python" "$worker_script" runtime-preflight
