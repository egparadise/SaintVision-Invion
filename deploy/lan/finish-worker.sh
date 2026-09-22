#!/usr/bin/env bash
set -euo pipefail
umask 077
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
node_id=$(python3 -c 'import json; print(json.load(open("manifest.json"))["nodeId"])')
[[ "$node_id" =~ ^nod_[0-9A-HJKMNP-TV-Z]{26}$ ]] || exit 1
worker_root="$HOME/.local/share/saintvision/$node_id"
[[ -f "$worker_root/node-key.pem" ]] || { echo 'Run Prepare-Worker.ps1 first'; exit 1; }
python3 worker_config.py topology manifest.json
python3 worker_config.py identity "$worker_root/manifest.json" manifest.json
if [[ $# -ne 0 ]]; then
    [[ $# -eq 2 ]] || exit 1
    [[ -f storage-policy.json && ! -L storage-policy.json ]] || exit 1
    if docker container inspect "saintvision-${node_id,,}" >/dev/null 2>&1; then
        echo 'Existing Node preserved; storage replacement requires a controlled upgrade.'
        exit 1
    fi
fi
cp -- node-cert.pem manifest.json ca.pem signer.pub peer-policy.json start-node.sh node-agent.tar worker_config.py worker_storage.py worker_replacement.py worker_replace.py "$worker_root/"
if [[ $# -ne 0 ]]; then
    cp -- storage-policy.json "$worker_root/"
fi
bash "$worker_root/start-node.sh" "$@"
