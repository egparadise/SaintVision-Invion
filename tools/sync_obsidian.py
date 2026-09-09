"""Conservative one-way export; never deletes files or overwrites unknown edits."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def contained(root, relative):
    candidate = root / relative
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root.resolve()) or '.obsidian' in candidate.parts:
        raise ValueError(f'Unsafe destination: {relative}')
    return candidate


def export(source, destination, state_path, original_hashes, apply=False, adopt=False):
    source, destination = source.resolve(), destination.resolve()
    if source == destination or source.is_relative_to(destination) or destination.is_relative_to(source):
        raise ValueError('Source and destination must be separate trees')
    state = json.loads(state_path.read_text('utf-8')) if state_path.is_file() else {'vault': str(destination), 'files': {}}
    if Path(state['vault']).resolve() != destination:
        raise ValueError('State belongs to another vault; use a separate --state path')
    changes, expected, conflicts = [], {}, []
    paths = sorted(p for p in source.rglob('*') if p.is_file())
    for path in paths:
        if not path.resolve().is_relative_to(source):
            raise ValueError('Source symlink outside source root')
        rel = path.relative_to(source).as_posix()
        target = contained(destination, rel)
        current, wanted = sha(target), sha(path)
        expected[rel] = current
        known = state['files'].get(rel, original_hashes.get(rel))
        if current == wanted:
            # Identical copies may be adopted without rewriting any destination bytes.
            if adopt or rel in state['files'] or current is None or current == known:
                state['files'][rel] = wanted
            continue
        if current is not None and current != known:
            conflicts.append(rel)
        else:
            changes.append((path, target, rel, wanted))
    if conflicts:
        raise ValueError('External edits or unmanaged collisions; no writes performed:\n' + '\n'.join(conflicts))
    if not apply:
        print(f'CHECK: {len(paths)} managed files, {len(changes)} pending exports, 0 conflicts. No writes.')
        return len(changes)
    destination.mkdir(parents=True, exist_ok=True)
    # Preflight every file again before the first mutation.
    for rel, before in expected.items():
        if sha(contained(destination, rel)) != before:
            raise ValueError(f'Changed during preflight: {rel}; no writes performed')
    for path, target, rel, wanted in changes:
        contained(destination, rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        if sha(target) != expected[rel]:
            raise ValueError(f'Changed during export: {rel}; prior exported files preserved')
        fd, temporary = tempfile.mkstemp(prefix='.inv-sync-', dir=target.parent)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(path.read_bytes())
            if sha(target) != expected[rel]:
                raise ValueError(f'Concurrent edit: {rel}')
            os.replace(temporary, target)
        finally:
            if Path(temporary).exists():
                Path(temporary).unlink()
        state['files'][rel] = wanted
        # Save progress per file so an interrupted export can be resumed.
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for path in paths:
        rel = path.relative_to(source).as_posix()
        if sha(contained(destination, rel)) != sha(path):
            raise ValueError(f'Post-export hash mismatch: {rel}')
        state['files'][rel] = sha(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'EXPORTED: {len(changes)} files; all {len(paths)} destination hashes match. Unmanaged files untouched.')
    return len(changes)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--check', action='store_true')
    action.add_argument('--apply', action='store_true')
    parser.add_argument('--vault', type=Path)
    parser.add_argument('--state', type=Path, default=ROOT / '.work/obsidian-sync-state.json')
    parser.add_argument('--adopt-identical', action='store_true')
    args = parser.parse_args()
    manifest = json.loads((ROOT / 'docs/source-manifest.json').read_text('utf-8'))
    export(ROOT / 'docs/vault', args.vault or Path(manifest['vault']), args.state,
           {item['path']: item['sha256'] for item in manifest['files']}, args.apply, args.adopt_identical)
