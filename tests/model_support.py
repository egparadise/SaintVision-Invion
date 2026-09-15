import hashlib
from inv.ids import new_id


def model_body(node, locations, chunks):
    offset, shards, replicas = 0, [], []
    for index, (location, chunk) in enumerate(zip(locations, chunks)):
        shards.append(
            {
                "index": index,
                "offset": offset,
                "byteLength": len(chunk),
                "sha256": hashlib.sha256(chunk).hexdigest(),
            }
        )
        replicas.append(
            {
                "shardIndex": index,
                "locationId": location,
                "locationVersion": 1,
                "nodeId": node,
                "state": "verified",
            }
        )
        offset += len(chunk)
    return {
        "modelId": new_id("mdl"),
        "version": "1.0.0",
        "format": "raw-bytes",
        "totalBytes": offset,
        "contentHash": hashlib.sha256(b"".join(chunks)).hexdigest(),
        "shards": shards,
        "replicas": replicas,
        "runtimeCompatibility": [
            {"adapter": "python-files", "version": "1", "modes": ["single-node"]}
        ],
        "licensePolicy": "local-test-only",
        "classification": "internal",
        "encryption": "none",
        "keyRef": None,
    }
