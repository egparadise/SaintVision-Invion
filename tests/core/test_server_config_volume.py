"""No credential files outside the explicit configuration may enter a volume."""
import importlib.util
import json
import os
import time
from uuid import uuid4
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("prepare_server_config", ROOT / "tools/prepare_server_config.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.mark.parametrize("reference", ["/outside/key", "/run/saintvision/../key", "/run/saintvision/api.json", "/run/saintvision/a/b"])
def test_outside_and_aliased_references_refused(tmp_path, reference):
    (tmp_path / "api.json").write_text(json.dumps({"identity": {"jwks_file": reference}}))
    with pytest.raises(ValueError):
        module.collect(tmp_path)


def test_unreferenced_private_files_never_copied(tmp_path):
    (tmp_path / "api.json").write_text(json.dumps({"identity": {"jwks_file": "/run/saintvision/jwks.json"}}))
    (tmp_path / "jwks.json").write_text("{}")
    (tmp_path / "unrelated-key.pem").write_text("synthetic-unrelated-secret")
    files, private = module.collect(tmp_path)
    assert set(files) == {"api.json", "jwks.json"} and not private


@pytest.mark.parametrize("expired", [False, True])
def test_real_volume_copy_or_failure_cleanup(tmp_path, expired):
    image = os.environ.get("INV_TEST_CONFIG_IMAGE")
    if not image:
        pytest.skip("Explicit pinned local candidate image required")
    from jwt_support import jwt_fixture
    identity = jwt_fixture(tmp_path, str(uuid4()))
    if expired:
        identity.bundle['expiresAt'] = int(time.time()) - 1
        identity.path.write_text(json.dumps(identity.bundle))
    (tmp_path / 'api.json').write_text(json.dumps({'identity': {
        'tenant_id': identity.tenant, 'issuer': identity.issuer, 'audience': identity.audience,
        'client_ids': ['synthetic-web'], 'jwks_file': '/run/saintvision/jwks.json'}}))
    original = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    volume = 'sv-config-test-' + uuid4().hex
    try:
        if expired:
            with pytest.raises(RuntimeError):
                module.prepare(tmp_path, volume, image)
            assert volume not in module.docker('volume', 'ls', '--format', '{{.Name}}').splitlines()
        else:
            receipt = module.prepare(tmp_path, volume, image)
            assert receipt['filesVerified'] == 2 and receipt['serverStarted'] is False
            with pytest.raises(ValueError, match='never be overwritten'):
                module.prepare(tmp_path, volume, image)
        assert original == {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    finally:
        if volume in module.docker('volume', 'ls', '--format', '{{.Name}}').splitlines():
            label = module.docker('volume', 'inspect', '--format', '{{index .Labels "ai.saintvision.config"}}', volume)
            assert len(label) == 32
            module.docker('volume', 'rm', volume)
