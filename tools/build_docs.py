"""Package reviewed documents and machine-readable traceability for review."""
from pathlib import Path
import zipfile

root = Path(__file__).resolve().parents[1]
target = root / 'dist/saintvision-guidelines.zip'
target.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
    for folder in ['docs/vault', 'ontology', 'skills']:
        for path in sorted((root/folder).rglob('*')):
            if path.is_file():
                archive.write(path, path.relative_to(root).as_posix())
    for name in ['AGENTS.md', 'CLAUDE.md', 'GEMINI.md', 'docs/task-registry.json', 'docs/source-manifest.json']:
        archive.write(root/name, name)
print(f'BUILT: {target.name}, {target.stat().st_size} bytes. Documentation only.')
