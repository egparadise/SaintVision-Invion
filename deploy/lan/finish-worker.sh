#!/usr/bin/env bash
set -euo pipefail
umask 077
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
node_id=$(python3 -c 'import json; print(json.load(open("manifest.json"))["nodeId"])')
[[ "$node_id" =~ ^nod_[0-9A-HJKMNP-TV-Z]{26}$ ]] || exit 1
worker_root="$HOME/.local/share/saintvision/$node_id"
[[ -f "$worker_root/node-key.pem" ]] || { echo 'Run Prepare-Worker.ps1 first'; exit 1; }
cmp manifest.json "$worker_root/manifest.json"
cp -- node-cert.pem "$worker_root/node-cert.pem"
bash "$worker_root/start-node.sh"
