import base64, hashlib, json
import pytest
from inv.output_ingestion import output_bytes
from inv.errors import DomainError


@pytest.mark.parametrize(
    "change", ["hash", "size", "truncated", "large", "invalid_stream", "duplicate_keys"]
)
def test_tampered_or_incomplete_streams_never_become_evidence(change):
    artifact = {"stdout": "", "stderr": "", "truncated": False}
    if change == "truncated":
        artifact["truncated"] = True
    if change == "large":
        artifact["stdout"] = base64.b64encode(b"x" * 65537).decode()
    if change == "invalid_stream":
        artifact["stderr"] = "!"
    data = json.dumps(artifact).encode()
    if change == "duplicate_keys":
        data = b'{"stdout":"","stderr":"","truncated":true,"truncated":false}'
    output = {
        "data": base64.b64encode(data).decode(),
        "sha256": hashlib.sha256(data).hexdigest(),
        "sizeBytes": len(data),
    }
    if change == "hash":
        output["sha256"] = "0" * 64
    if change == "size":
        output["sizeBytes"] += 1
    with pytest.raises(DomainError, match="VERIFY-0023"):
        output_bytes({"output": output})
