#!/usr/bin/env bash
set -euo pipefail
umask 077
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
for file in manifest.json node-cert.pem node-key.pem ca.pem signer.pub peer-policy.json; do
    [[ -f "$file" && ! -L "$file" ]] || { echo "Missing or unsafe $file"; exit 1; }
done
openssl verify -CAfile ca.pem -purpose sslserver node-cert.pem
openssl x509 -in node-cert.pem -checkend 60 -noout
[[ "$(openssl pkey -in node-key.pem -pubout | sha256sum)" == "$(openssl x509 -in node-cert.pem -pubkey -noout | sha256sum)" ]] || { echo 'Certificate and private key differ'; exit 1; }
mapfile -t cfg < <(python3 -c 'import json; d=json.load(open("manifest.json")); print("\n".join(str(d[k]) for k in ("nodeId","tenantId","epoch","agentImage","nodeIP","nodePort")))')
node_id=${cfg[0]}
[[ "$node_id" =~ ^nod_[0-9A-HJKMNP-TV-Z]{26}$ ]] || exit 1
# Reload into the engine used by this invocation before creating any state.
# A classic-store config ID may not address an imported containerd-store image.
timeout 120 docker load -i node-agent.tar
image_tag=$(python3 -c 'import json; print(json.load(open("manifest.json"))["agentTag"])')
docker image inspect "$image_tag" > image-inspect.json
actual_image=$(python3 worker_config.py image manifest.json image-inspect.json)
name="saintvision-${node_id,,}"
volume="$name-state"
if docker container inspect "$name" >/dev/null 2>&1; then
    echo "Container $name already exists. Preserve its journal; use docker start only after checking its status."
    exit 1
fi
if docker volume inspect "$volume" >/dev/null 2>&1; then
    [[ "$(docker volume inspect --format '{{index .Labels "ai.saintvision.node"}}' "$volume")" == "$node_id" ]] || { echo 'Volume ownership differs'; exit 1; }
    [[ -z "$(docker ps -aq --filter "volume=$volume")" ]] || { echo 'Volume is used by another container'; exit 1; }
    echo 'Resuming with the existing owned volume; the Node validates its journal identity and epoch.'
else
    docker volume create --label "ai.saintvision.node=$node_id" "$volume" >/dev/null
fi
docker create --name "$name" --label "ai.saintvision.node=$node_id" \
    --restart unless-stopped --read-only --cap-drop ALL --security-opt no-new-privileges \
    --pids-limit 128 --memory 256m --cpus 0.5 \
    --publish "${cfg[4]}:${cfg[5]}:18443" \
    --mount "type=volume,source=$volume,target=/state" \
    "$actual_image" --serve --listen 0.0.0.0:18443 \
    --tenant "${cfg[1]}" --node "$node_id" --epoch "${cfg[2]}" \
    --profile lan-observe-v1 --image "${cfg[3]}" --executable /inv-node \
    --state /state/journal --public-key /state/signer.pub \
    --tls-cert /state/node-cert.pem --tls-key /state/node-key.pem \
    --client-ca /state/ca.pem --peer-policy /state/peer-policy.json >/dev/null
for file in node-cert.pem node-key.pem ca.pem signer.pub peer-policy.json; do
    chmod 600 "$file"
    docker cp "$file" "$name:/state/$file"
done
docker start "$name"
echo 'Node container started. Connection is complete only after the server verifies mTLS observations.'
