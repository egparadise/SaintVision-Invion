"""Opt-in candidate image acceptance; only disposable Docker resources are touched."""
import json
import os
import subprocess
import time
from uuid import uuid4

import httpx
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo, conninfo_to_dict
from sqlalchemy.engine import URL
import pytest
from inv.ids import new_id
from jwt_support import jwt_fixture
from saintvision.ids import new_id as business_id

pytestmark = pytest.mark.postgres

# Runs in an isolated initialization container; all generated keys are synthetic.
PREPARE = r'''
import json,sys,os
from pathlib import Path
from datetime import datetime,timedelta,timezone
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
p=Path('/config'); data=json.load(sys.stdin)
for name,body in data['files'].items():
    f=p/name; f.write_text(json.dumps(body)); f.chmod(0o600); os.chown(f,65532,65532)
if data['workspace']:
    key=Ed25519PrivateKey.generate()
    name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'synthetic-container-test')])
    now=datetime.now(timezone.utc)
    cert=(x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
          .serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=1))
          .not_valid_after(now+timedelta(hours=1)).add_extension(x509.BasicConstraints(ca=True,path_length=None),True)
          .sign(key,None))
    (p/'tls.pem').write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    for filename in ('tls-key.pem','signer.pem'):
        (p/filename).write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    for filename in ('tls.pem','tls-key.pem','signer.pem'):
        (p/filename).chmod(0o600); os.chown(p/filename,65532,65532)
if data['case']=='unreadable': os.chown(p/'api.json',0,0)
if data['case']=='writable': (p/'api.json').chmod(0o660)
if data['case']=='public-signing-key': (p/'signer.pem').chmod(0o644)
'''


def docker(*args, env=None, data=None):
    result = subprocess.run(["docker", *args], input=data, env=env, capture_output=True,
                            text=True, timeout=90)
    assert result.returncode == 0, "Docker operation failed; diagnostics suppressed"
    return result.stdout.strip()


@pytest.fixture
def business_login(env):
    role, password = "inv_candidate_" + uuid4().hex, uuid4().hex
    with psycopg.connect(env.owner) as conn:
        conn.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOBYPASSRLS").format(
            sql.Identifier(role), sql.Literal(password)))
        conn.execute(sql.SQL("GRANT inv_app TO {}").format(sql.Identifier(role)))
    try:
        yield role, password
    finally:
        with psycopg.connect(env.owner) as conn:
            conn.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))


@pytest.mark.parametrize("case", ["healthy", "workspace", "unreadable", "writable", "public-signing-key",
                                  "business", "business-workspace", "business-kernel-role"])
def test_candidate_nonroot_configuration_and_workspace(env, tmp_path, case, business_login):
    image = os.environ.get("INV_TEST_SERVER_IMAGE")
    database_host = os.environ.get("INV_CONTAINER_TEST_DB_HOST")
    if not image or not database_host:
        pytest.skip("Explicit candidate image and disposable container DB address required")
    identity = jwt_fixture(tmp_path, env.tenant)
    business = case.startswith("business")
    with psycopg.connect(env.owner) as conn:
        conn.execute("INSERT INTO inv.project_grants(tenant_id,project_id,subject_id,can_request,can_approve)"
                     " VALUES(%s,%s,%s,true,false)", (env.tenant, env.project, identity.subject("requester")))
        if business:
            conn.execute("INSERT INTO public.tenants(tenant_id,slug,display_name) VALUES(%s,%s,'candidate')",
                         (env.tenant, uuid4().hex))
            conn.execute("INSERT INTO public.users(tenant_id,user_id,external_subject,display_name) VALUES(%s,%s,%s,'candidate')",
                         (env.tenant, business_id('user'), identity.subject('requester')))
    workspace = case in {"workspace", "public-signing-key", "business-workspace"}
    config = {"identity": {"tenant_id": env.tenant, "issuer": identity.issuer,
                          "audience": identity.audience, "client_ids": ["synthetic-web"],
                          "jwks_file": "/run/saintvision/jwks.json"}}
    if business:
        config["business"] = True
    if workspace:
        config["workspace"] = {
            "workingRoot": "/workspaces", "nodeId": env.node,
            "resources": {"cpu": env.resource, "memory": new_id("res")},
            "profile": {"version": "synthetic-test-only", "images": ["sha256:" + "a" * 64],
                        "executables": ["/usr/local/bin/python"]},
            "policyVersion": "synthetic-test-only", "signingKeyFile": "/run/saintvision/signer.pem",
            "tls": {"ca_file": "/run/saintvision/tls.pem", "certificate_file": "/run/saintvision/tls.pem",
                    "key_file": "/run/saintvision/tls-key.pem"}}
    name = "sv-server-test-" + uuid4().hex
    container = None
    working_volume = None
    volume = docker("volume", "create", "--label", "ai.saintvision.test=" + name, name)
    try:
        docker("run", "--rm", "-i", "--network", "none", "--user", "0:0",
               "--mount", f"type=volume,source={volume},target=/config", image,
               "python", "-c", PREPARE,
               data=json.dumps({"files": {"api.json": config, "jwks.json": identity.bundle},
                                "workspace": workspace, "case": case}))
        child_env = {**os.environ, "INV_API_CONFIG": "/run/saintvision/api.json",
                     "INV_RUNTIME_DSN": make_conninfo(env.runtime, host=database_host, port=5432),
                     "INV_RECOVERY_EPOCH": env.epoch}
        info = conninfo_to_dict(env.runtime)
        role, password = business_login
        if case == "business-kernel-role":
            role, password = info['user'], info['password']
        child_env['INV_BUSINESS_DSN'] = URL.create('postgresql+psycopg', username=role,
            password=password, host=database_host, port=5432, database=info['dbname'],
            query={k: v for k, v in info.items() if k not in {'user', 'password', 'host', 'port', 'dbname'}}).render_as_string(hide_password=False)
        working_mount = ["--tmpfs", "/workspaces:uid=65532,gid=65532,mode=0700"]
        if case == 'business-workspace':
            working_volume = docker('volume', 'create', '--label', 'ai.saintvision.test=' + name, name + '-working')
            docker('run', '--rm', '--network', 'none', '--user', '0:0', '--mount',
                   f'type=volume,source={working_volume},target=/workspaces', image, 'python', '-c',
                   "import os; os.chown('/workspaces',65532,65532); os.chmod('/workspaces',0o700)")
            working_mount = ['--mount', f'type=volume,source={working_volume},target=/workspaces']
        container = docker("create", "--name", name, "--label", "ai.saintvision.test=" + name,
                           "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                           "--memory", "512m", "--cpus", "1", "--pids-limit", "128",
                           "--publish", "127.0.0.1::8080", "--tmpfs", "/tmp",
                           *working_mount,
                           "--mount", f"type=volume,source={volume},target=/run/saintvision,readonly",
                           "--env", "INV_API_CONFIG", "--env", "INV_RUNTIME_DSN",
                           "--env", "INV_RECOVERY_EPOCH", "--env", "INV_BUSINESS_DSN", image, env=child_env)
        docker("start", container)
        port = json.loads(docker("inspect", "--format", "{{json .NetworkSettings.Ports}}", container))["8080/tcp"][0]["HostPort"]
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False, timeout=2) as client:
            healthy = case in {"healthy", "workspace", "business", "business-workspace"}
            for _ in range(100):
                state = json.loads(docker("inspect", "--format", "{{json .State}}", container))
                if not state["Running"]:
                    assert not healthy and state["ExitCode"] != 0
                    return
                try:
                    response = client.get("/readyz")
                    assert healthy, "Unsafe configuration unexpectedly served HTTP"
                    assert response.status_code == 200
                    body = response.json()
                    assert body["workspaceAdmission"] == ("configured" if workspace else "not_configured")
                    assert body["executionDispatcher"] == ("external-worker-required" if workspace else "not_configured")
                    break
                except httpx.TransportError:
                    time.sleep(.1)
            else:
                pytest.fail("Candidate startup/expected rejection timed out")
            assert docker("exec", container, "id", "-u") == "65532"
            missing = client.get("/v1/projects")
            assert missing.status_code == 401
            assert missing.headers["WWW-Authenticate"] == "Bearer"
            if business:
                assert missing.json()["code"] == "AUTH-MISSING-CREDENTIAL"
            result = client.get("/v1/projects", headers={"Authorization": "Bearer " + identity.token()})
            assert result.status_code == 200
            if business:
                headers = {"Authorization": "Bearer " + identity.token(), "Idempotency-Key": uuid4().hex}
                project = client.post('/v1/projects', headers=headers,
                                      json={'code': 'candidate-' + uuid4().hex[:8], 'displayName': 'Candidate'})
                assert project.status_code == 201
                assert project.json()['kernelLinked'] is False
                project_id = project.json()['projectId']
                created = client.post('/v1/projects/' + project_id + '/workspaces', headers=headers, json={'name': 'candidate'})
                assert created.status_code == 201
                readiness = client.get('/v1/workspaces/' + created.json()['workspaceId'] + '/execution-readiness', headers=headers)
                assert readiness.status_code == 200 and readiness.json()['executable'] is False
                assert client.post('/v1/projects/' + project_id + '/runs', headers=headers, json={}).status_code == 403
                unknown = client.get('/v1/projects', headers={'Authorization': 'Bearer ' + identity.token('unknown')})
                assert unknown.status_code == 401 and unknown.headers['WWW-Authenticate'] == 'Bearer'
                assert unknown.json()['code'] == 'AUTH-INVALID-CREDENTIAL'
            else:
                assert result.json() == {"items": [{"projectId": env.project}]}
            write = subprocess.run(["docker", "exec", container, "python", "-c",
                                    "open('/run/saintvision/api.json','w')"], capture_output=True)
            assert write.returncode != 0
            if working_volume:
                code = ("from inv.workspace_files import WorkingGenerations; from pathlib import Path; "
                        "WorkingGenerations('/workspaces'); p=Path('/workspaces/synthetic-edit.txt'); "
                        "p.write_text('edited before restart'); p.chmod(0o600)")
                docker('exec', container, 'python', '-c', code)
                docker('restart', container)
                # Docker may assign a new ephemeral host port when restarting.
                port = json.loads(docker("inspect", "--format", "{{json .NetworkSettings.Ports}}", container))["8080/tcp"][0]["HostPort"]
                client.base_url = f"http://127.0.0.1:{port}"
                # New process re-opens the same service-owned volume and reads the edit.
                code = ("from inv.workspace_files import WorkingGenerations; from pathlib import Path; "
                        "WorkingGenerations('/workspaces'); "
                        "assert Path('/workspaces/synthetic-edit.txt').read_text() == 'edited before restart'")
                docker('exec', container, 'python', '-c', code)
                for _ in range(100):
                    try:
                        if client.get('/readyz').status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    time.sleep(.1)
                else:
                    pytest.fail('Persistent Workspace candidate failed after restart')
    finally:
        if container:
            assert docker("inspect", "--format", '{{index .Config.Labels "ai.saintvision.test"}}', container) == name
            docker("rm", "-f", container)
        assert docker("volume", "inspect", "--format", '{{index .Labels "ai.saintvision.test"}}', volume) == name
        docker("volume", "rm", volume)
        if working_volume:
            assert docker("volume", "inspect", "--format", '{{index .Labels "ai.saintvision.test"}}', working_volume) == name
            docker("volume", "rm", working_volume)
