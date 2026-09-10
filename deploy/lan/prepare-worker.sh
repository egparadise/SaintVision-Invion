#!/usr/bin/env bash
set -euo pipefail
umask 077
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
command -v openssl >/dev/null
command -v python3 >/dev/null
command -v docker >/dev/null
api=$(timeout 20 docker version --format '{{.Server.APIVersion}}')
python3 -c 'import sys; assert tuple(map(int, sys.argv[1].split("."))) >= (1,45), "Docker API 1.45 or newer is required"' "$api"
node_id=$(python3 -c 'import json; print(json.load(open("manifest.json"))["nodeId"])')
[[ "$node_id" =~ ^nod_[0-9A-HJKMNP-TV-Z]{26}$ ]] || exit 1
worker_root="$HOME/.local/share/saintvision/$node_id"
mkdir -p -- "$worker_root"
chmod 700 "$worker_root"
if [[ -f "$worker_root/manifest.json" ]]; then
    cmp manifest.json "$worker_root/manifest.json" || { echo 'Existing installation identity differs; preserve its state.'; exit 1; }
fi
cp -- manifest.json ca.pem signer.pub peer-policy.json start-node.sh node-agent.tar "$worker_root/"
if [[ ! -f "$worker_root/node-key.pem" ]]; then
    openssl genpkey -algorithm ED25519 -out "$worker_root/node-key.pem"
fi
chmod 600 "$worker_root/node-key.pem"
openssl req -new -key "$worker_root/node-key.pem" -subj "/CN=$node_id" -out "$worker_root/node.csr"
timeout 120 docker load -i "$worker_root/node-agent.tar"
echo 'Send ONLY the following public certificate request to the server operator:'
cat "$worker_root/node.csr"
echo "Private key remains in: $worker_root/node-key.pem"
