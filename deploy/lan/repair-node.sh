#!/usr/bin/env bash
set -euo pipefail
umask 077
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
node_id=$(python3 -c 'import json; print(json.load(open("manifest.json"))["nodeId"])')
[[ "$node_id" =~ ^nod_[0-9A-HJKMNP-TV-Z]{26}$ ]] || exit 1
worker_root="$HOME/.local/share/saintvision/$node_id"
name="saintvision-${node_id,,}"
python3 worker_config.py identity "$worker_root/manifest.json" manifest.json
docker inspect "$name" > "$worker_root/container-inspect.json"
python3 worker_config.py repair-target manifest.json "$worker_root/container-inspect.json"
[[ "$(docker volume inspect --format '{{index .Labels "ai.saintvision.node"}}' "$name-state")" == "$node_id" ]] || { echo 'Volume ownership differs'; exit 1; }
python3 worker_config.py install-files "$name" "$worker_root"
docker start "$name"
python3 worker_config.py check-running "$name"
