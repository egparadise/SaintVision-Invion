"""Unmodified reviewer probe; fail when its released-claim defect is present."""
import json,subprocess,sys
from pathlib import Path
E=Path(__file__).resolve().parent
p=subprocess.run([sys.executable,'-B',str(E/'prior-reviewer_tf_released_claim_probe.py.txt'),sys.argv[1]],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
sys.stdout.buffer.write(p.stdout);sys.stderr.buffer.write(p.stderr)
if p.returncode:raise SystemExit(p.returncode)
d=json.loads(p.stdout);raise SystemExit(1 if d['defect'] else 0)
