"""Source/data/docs gates only; never imports or executes product or test code."""
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = Path.cwd()
PYTHON = 'D:/Project/SaintVisionI-Invion/.venv/Scripts/python.exe'
BASE = '96afd799d49717fd40e4ddabd538d82accbe1958'
SYNC = Path('D:/Project/SaintVision-Invion/SaintVisionI-Invion/.git/obsidian-sync-state.json')
commands = [
    [PYTHON, '-B', 'tools/check_docs.py'],
    [PYTHON, '-B', 'tools/check_ontology.py'],
    [PYTHON, '-B', 'tools/check_doc_path_citations.py', '--ratchet', '--base-ref', BASE],
    [PYTHON, '-B', 'tools/check_doc_single_source.py', '--ratchet'],
    [PYTHON, '-B', 'tools/check_contract_bindings.py'],
    [PYTHON, '-B', 'tools/check_frontend_integrity.py'],
    [PYTHON, '-B', 'tools/sync_obsidian.py', '--check'],
    ['git', 'diff', '--check'],
]
records = []
for argv in commands:
    start = datetime.now(timezone(timedelta(hours=9))).isoformat()
    result = subprocess.run(argv, capture_output=True, env={**__import__('os').environ, 'PYTHONUTF8': '1'})
    record = dict(argv=argv, atKST=start, exit=result.returncode,
                  stdout=result.stdout.decode('utf8', errors='replace'), stderr=result.stderr.decode('utf8', errors='replace'))
    records.append(record)
    (HERE/'local-gates.json').write_text(json.dumps(records, indent=2, ensure_ascii=True)+'\n', encoding='utf8')
    print(json.dumps(dict(argv=argv, exit=result.returncode, stdoutTail=record["stdout"][-500:])), flush=True)
    if result.returncode != 0:
        sys.exit(result.returncode)
before = (HERE/'sync-state-before.json').read_bytes()
after = SYNC.read_bytes()
(HERE/'sync-state-after.json').write_bytes(after)
comparison = dict(fullBytesEqual=before == after, beforeBytes=len(before), afterBytes=len(after),
                  beforeSHA256=hashlib.sha256(before).hexdigest(), afterSHA256=hashlib.sha256(after).hexdigest(), checkOnly=True)
(HERE/'sync-state-comparison.json').write_text(json.dumps(comparison, indent=2)+'\n', encoding='utf8')
print(json.dumps(comparison), flush=True)
assert before == after, 'Canonical sync state changed; Root must reconcile without worker APPLY'
