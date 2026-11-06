"""Hardened requirement wrapper; original reviewer probe remains byte-exact."""
import json,subprocess,sys
from pathlib import Path
E=Path(__file__).resolve().parent
try:
    target=Path(sys.argv[1]).resolve(strict=True)
    if not target.is_dir() or not (target/'model.py').is_file() or not (target/'model.py').resolve().is_relative_to(target):raise ValueError('model outside requested directory')
except (IndexError,OSError,ValueError):
    print('INVALID_MODEL_DIRECTORY',file=sys.stderr);raise SystemExit(2)
probe=E/'prior-reviewer_tf_released_claim_probe.py.txt'
guard="""import sys,runpy
from pathlib import Path
probe,target=sys.argv[1:3]
sys.path.insert(0,target)
import model
if not Path(model.__file__).resolve().is_relative_to(Path(target).resolve()):
    raise SystemExit('IMPORTED_MODEL_OUTSIDE_REQUESTED_DIRECTORY')
sys.argv=[probe,target]
runpy.run_path(probe,run_name='__main__')
"""
p=subprocess.run([sys.executable,'-B','-c',guard,str(probe),str(target)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
sys.stdout.buffer.write(p.stdout);sys.stderr.buffer.write(p.stderr)
if p.returncode:raise SystemExit(p.returncode)
d=json.loads(p.stdout);raise SystemExit(1 if d['defect'] else 0)
