"""Conservative one-way export; never deletes files or overwrites unknown edits."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


class ConflictsDetected(Exception):
    """Destination files diverged from the tracked baseline.

    This is a *diagnostic result*, not a crash: no writes were performed and the
    caller decides how to surface it. It is deliberately distinct from the
    ValueErrors that signal a usage/configuration error (unsafe path, wrong
    state vault, mid-run change), so the exit code can tell them apart.
    """

    def __init__(self, conflicts):
        self.conflicts = conflicts  # list of (rel, reason)
        super().__init__(f'{len(conflicts)} unmanaged destination collisions; no writes performed')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def contained(root, relative):
    candidate = root / relative
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root.resolve()) or '.obsidian' in candidate.parts:
        raise ValueError(f'Unsafe destination: {relative}')
    return candidate


def _conflict_reason(current, wanted, known):
    # Same collision the tool always refused to overwrite, now labelled so the
    # 'why' is legible instead of an opaque 675-line dump.
    if known is None:
        # No manifest entry and no export-state record: the tool has no baseline
        # to decide whether the destination bytes are a real user edit or just an
        # un-recorded prior sync. Fail-closed and report it as such.
        return 'no-baseline'
    if wanted == known:
        # Source matches the baseline but the destination changed -> a genuine
        # external (vault-side) edit.
        return 'destination-edited'
    if current != wanted:
        # Source and destination both moved away from the baseline.
        return 'both-diverged'
    return 'other'


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
            conflicts.append((rel, _conflict_reason(current, wanted, known)))
        else:
            changes.append((path, target, rel, wanted))
    if conflicts:
        # A diagnostic outcome, not a crash: no writes have happened at this point
        # (this is before any mutation), so both --check and --apply stay fail-closed.
        raise ConflictsDetected(conflicts)
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


def _report_conflicts(conflicts, out_path):
    """Group conflicts by reason, print a summary, and write the full list to a file.

    Returns the exit code (3): a judgment result (collisions), distinct from a
    usage/config error (1) and clean success (0).
    """
    counts = {}
    for _, reason in conflicts:
        counts[reason] = counts.get(reason, 0) + 1
    print(f'CONFLICTS: {len(conflicts)} unmanaged destination collisions; no writes performed.', file=sys.stderr)
    print('  grouped by reason:', file=sys.stderr)
    for reason, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f'    {n:6}  {reason}', file=sys.stderr)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            {'reasonCounts': counts,
             'conflicts': [{'path': rel, 'reason': reason} for rel, reason in conflicts]},
            ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8')
    print(f'  full list ({len(conflicts)}): {out_path}', file=sys.stderr)
    print('  no-baseline = the tool has no manifest/state record for these; it cannot tell a real '
          'edit from an un-recorded prior sync. Establish a state baseline before --apply.',
          file=sys.stderr)
    return 3


def main(argv=None):
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--check', action='store_true')
    action.add_argument('--apply', action='store_true')
    parser.add_argument('--vault', type=Path)
    parser.add_argument('--state', type=Path, default=ROOT / '.work/obsidian-sync-state.json')
    parser.add_argument('--conflicts-out', type=Path, default=ROOT / '.work/obsidian-sync-conflicts.json')
    parser.add_argument('--adopt-identical', action='store_true')
    args = parser.parse_args(argv)
    try:
        manifest = json.loads((ROOT / 'docs/source-manifest.json').read_text('utf-8'))
    except (OSError, ValueError) as exc:
        print(f'Manifest unavailable ({type(exc).__name__}); cannot sync.', file=sys.stderr)
        return 1
    try:
        export(ROOT / 'docs/vault', args.vault or Path(manifest['vault']), args.state,
               {item['path']: item['sha256'] for item in manifest['files']}, args.apply, args.adopt_identical)
    except ConflictsDetected as detected:
        return _report_conflicts(detected.conflicts, args.conflicts_out)
    except ValueError as exc:
        # Usage/configuration/mid-run error -- distinct from a conflict diagnostic.
        print(f'Sync error ({type(exc).__name__}): {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
