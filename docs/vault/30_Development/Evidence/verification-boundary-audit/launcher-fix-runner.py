"""Execute remediated deploy_intranet.ps1 with native-command stand-ins in a temp tree to generate fix evidence."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "docs/vault/30_Development/Evidence/verification-boundary-audit/launcher-fix-results.json"
source = ROOT / "tools/deploy_intranet.ps1"
results = []

for case, failed in [
    ("tls-failure", "python"),
    ("tests-failure", "npm"),
    ("smoke-failure", "node"),
    ("compose-failure", "docker"),
    ("success", None),
]:
    with tempfile.TemporaryDirectory(prefix="sv-launcher-audit-fix-") as folder:
        work = Path(folder)
        for d in ["tools", ".venv/Scripts", "apps/web/dist", "deploy/certs", "bin"]:
            (work / d).mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, work / "tools/deploy_intranet.ps1")
        (work / "README.md").write_text("# Test README\n", encoding="utf-8")
        (work / "docker-compose.prod.yml").write_text("version: '3.8'\nservices: {}\n", encoding="utf-8")

        # Mock tools/generate_tls_cert.py
        mock_py = work / "tools/generate_tls_cert.py"
        trace_file = work / "trace.txt"
        if failed == "python":
            mock_py.write_text(
                f'import sys\nwith open(r"{trace_file}", "a") as f: f.write("python tools/generate_tls_cert.py\\n")\nsys.exit(23)\n',
                encoding="utf-8",
            )
        else:
            mock_py.write_text(
                f'import sys\nfrom pathlib import Path\nwith open(r"{trace_file}", "a") as f: f.write("python tools/generate_tls_cert.py\\n")\n'
                'p = Path("deploy/certs")\np.mkdir(parents=True, exist_ok=True)\n'
                '(p / "saintvision.crt").write_text("mock-cert")\n(p / "saintvision.key").write_text("mock-key")\n',
                encoding="utf-8",
            )

        for name in ["npm", "node", "docker"]:
            path = work / ("bin/" + name + ".cmd")
            gen_dist = ""
            if name == "npm" and failed != "npm":
                gen_dist = 'echo mock-html > "%~dp0..\\apps\\web\\dist\\index.html"\n'

            script_body = (
                "@echo off\n"
                f'echo {name} %*>>"{trace_file}"\n'
            )
            if name == failed:
                script_body += "exit /b 23\n"
            else:
                script_body += gen_dist
                script_body += "exit /b 0\n"

            path.write_text(script_body)

        (work / "entry.ps1").write_text(
            "$ErrorActionPreference='Stop'\n"
            "function Invoke-WebRequest { [pscustomobject]@{StatusCode=200} }\n"
            "& ./tools/deploy_intranet.ps1\n",
            encoding="utf-8",
        )
        env = {**os.environ, "PATH": str(work / "bin") + os.pathsep + os.environ["PATH"]}
        child = subprocess.run(
            [shutil.which("powershell.exe") or "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(work / "entry.ps1")],
            cwd=work,
            env=env,
            capture_output=True,
            timeout=30,
        )
        output = child.stdout.decode(errors="replace")
        trace = trace_file.read_text().splitlines() if trace_file.exists() else []
        result = {
            "case": case,
            "injectedNativeExit": 23 if failed else 0,
            "processExit": child.returncode,
            "zeroErrorsBanner": "ZERO Errors (All Exit Codes 0)" in output,
            "honestSummaryBanner": "[API Contract Smoke Suite / Local Preflight Pipeline Summary]" in output,
            "trace": trace,
            "sourceUnchanged": (work / "tools/deploy_intranet.ps1").read_bytes() == source.read_bytes(),
        }
        assert result["sourceUnchanged"]
        if failed is None:
            assert child.returncode == 0
            assert result["honestSummaryBanner"]
            assert not result["zeroErrorsBanner"]
        else:
            assert child.returncode == 1
            assert not result["zeroErrorsBanner"]
            assert not result["honestSummaryBanner"]
        results.append(result)

evidence = {
    "scope": "Windows PowerShell remediated launcher, synthetic native command injection and HTTP stub; no production deployment",
    "remediation": "VB-LAUNCH-01",
    "sourceSHA256": hashlib.sha256(source.read_bytes()).hexdigest(),
    "results": results,
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(evidence, indent=2) + "\n")
print(json.dumps(evidence, indent=2))
