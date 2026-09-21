"""Conservative one-way export; never deletes files or overwrites unknown edits."""
from pathlib import Path, PurePosixPath, PureWindowsPath
import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


class ConflictsDetected(Exception):
    """Destination files diverged from the tracked baseline.

    This is a *diagnostic result*, not a crash: unlisted vault files were not
    written; explicitly listed resolutions and identical-file metadata may have
    been persisted. The caller decides how to surface it. It is deliberately distinct from the
    ValueErrors that signal a usage/configuration error (unsafe path, wrong
    state vault, mid-run change), so the exit code can tell them apart.
    """

    def __init__(self, conflicts, adopted=(), resolved=()):
        self.conflicts = conflicts  # list of (rel, reason)
        self.adopted = tuple(adopted)
        self.resolved = tuple(resolved)
        super().__init__(f'{len(conflicts)} unmanaged destination collisions remain')


def default_state_path(root=None):
    """Keep one export baseline in shared Git metadata for the single vault."""
    root = Path(root or ROOT).resolve()
    result = subprocess.run(
        ['git', 'rev-parse', '--git-common-dir'],
        cwd=root, check=True, capture_output=True, text=True)
    common_dir = Path(result.stdout.strip())
    if not common_dir.is_absolute():
        common_dir = root / common_dir
    return common_dir.resolve() / 'obsidian-sync-state.json'


def _write_state(state_path, state):
    """Atomically persist local export metadata without touching vault files."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.obsidian-sync-state-', dir=state_path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            stream.write(json.dumps(state, ensure_ascii=False, indent=2) + '\n')
        os.replace(temporary, state_path)
    finally:
        if Path(temporary).exists():
            Path(temporary).unlink()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def sync_sha(path):
    """Hash comparison content with CRLF normalized to LF; never writes bytes."""
    if not path.is_file():
        return None
    content = path.read_bytes().replace(b'\r\n', b'\n')
    return hashlib.sha256(content).hexdigest()


def _matches_baseline(path, known):
    """Accept normalized hashes and legacy raw-byte state/manifest hashes."""
    return known is not None and known in (sha(path), sync_sha(path))


def read_conflict_paths(path):
    """Read canonical docs/vault-relative paths, one UTF-8 line per file."""
    lines = Path(path).read_text(encoding='utf-8-sig').splitlines()
    selected = []
    seen = set()
    for line_number, rel in enumerate(lines, start=1):
        if not rel:
            continue
        pure = PurePosixPath(rel)
        parts = rel.split('/')
        if (rel != rel.strip() or '\\' in rel or pure.is_absolute()
                or PureWindowsPath(rel).drive
                or any(part in ('', '.', '..') for part in parts)
                or any(part.lower() == '.obsidian' for part in parts)
                or pure.as_posix() != rel):
            raise ValueError(f'Invalid repository-relative path on line {line_number}')
        if rel in seen:
            raise ValueError(f'Duplicate conflict path on line {line_number}')
        seen.add(rel)
        selected.append(rel)
    if not selected:
        raise ValueError('Conflict path list is empty')
    return tuple(selected)


def contained(root, relative):
    candidate = root / relative
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root.resolve()) or '.obsidian' in candidate.parts:
        raise ValueError(f'Unsafe destination: {relative}')
    return candidate


def _conflict_reason(known, source_matches_baseline):
    # Same collision the tool always refused to overwrite, now labelled so the
    # 'why' is legible instead of an opaque 675-line dump.
    if known is None:
        # No manifest entry and no export-state record: the tool has no baseline
        # to decide whether the destination bytes are a real user edit or just an
        # un-recorded prior sync. Fail-closed and report it as such.
        return 'no-baseline'
    if source_matches_baseline:
        # Source matches the baseline but the destination changed -> a genuine
        # external (vault-side) edit.
        return 'destination-edited'
    # Source and destination both moved away from the baseline.
    return 'both-diverged'


def _replace_from_source(source_path, target, expected_source_raw, expected_target_raw):
    """Atomically write source bytes only if neither side changed since scan."""
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.inv-sync-', dir=target.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(source_path.read_bytes())
        if sha(source_path) != expected_source_raw:
            raise ValueError('Source changed during export; no replacement performed')
        if sha(target) != expected_target_raw:
            raise ValueError('Destination changed during export; no replacement performed')
        os.replace(temporary, target)
    finally:
        if Path(temporary).exists():
            Path(temporary).unlink()


def export(source, destination, state_path, original_hashes, apply=False, adopt=False,
           resolve_conflicts=None):
    if resolve_conflicts is not None and not apply:
        raise ValueError('Conflict path resolution requires apply=True')
    if resolve_conflicts is not None and not resolve_conflicts:
        raise ValueError('Conflict resolution list is empty')
    if resolve_conflicts is not None and any(not isinstance(rel, str) for rel in resolve_conflicts):
        raise ValueError('Conflict resolution paths must be strings')
    source, destination = source.resolve(), destination.resolve()
    if source == destination or source.is_relative_to(destination) or destination.is_relative_to(source):
        raise ValueError('Source and destination must be separate trees')
    state = json.loads(state_path.read_text('utf-8')) if state_path.is_file() else {'vault': str(destination), 'files': {}}
    if Path(state['vault']).resolve() != destination:
        raise ValueError('State belongs to another vault; use a separate --state path')
    changes, expected, expected_raw, source_raw, conflicts, adopted = [], {}, {}, {}, [], []
    if resolve_conflicts is not None and len(resolve_conflicts) != len(set(resolve_conflicts)):
        raise ValueError('Conflict resolution list contains duplicate paths')
    paths = sorted(p for p in source.rglob('*') if p.is_file())
    for path in paths:
        if not path.resolve().is_relative_to(source):
            raise ValueError('Source symlink outside source root')
        rel = path.relative_to(source).as_posix()
        target = contained(destination, rel)
        current, wanted = sync_sha(target), sync_sha(path)
        current_raw = sha(target)
        expected_raw[rel] = current_raw
        source_raw[rel] = sha(path)
        expected[rel] = current
        known = state['files'].get(rel, original_hashes.get(rel))
        if current == wanted:
            # Identical copies may be adopted without rewriting any destination bytes.
            if adopt:
                state['files'][rel] = wanted
                adopted.append(rel)
            elif (rel in state['files'] or current is None
                  or _matches_baseline(target, known) or _matches_baseline(path, known)):
                state['files'][rel] = wanted
            continue
        if current_raw is not None and not _matches_baseline(target, known):
            conflicts.append((rel, _conflict_reason(known, _matches_baseline(path, known))))
        else:
            changes.append((path, target, rel, wanted))
    resolved_changes = []
    if resolve_conflicts is not None:
        current_conflicts = {rel: reason for rel, reason in conflicts}
        stale = sorted(set(resolve_conflicts) - set(current_conflicts))
        if stale:
            raise ValueError('Resolution list includes paths that are not current conflicts: '
                             + ', '.join(stale))
        requested = set(resolve_conflicts)
        resolved_changes = [
            (source / rel, contained(destination, rel), rel, sync_sha(source / rel))
            for rel in resolve_conflicts]
        unresolved = [(rel, reason) for rel, reason in conflicts if rel not in requested]
        if unresolved:
            # A partial resolution writes only explicitly listed conflicts. It does not
            # export unrelated pending files, and the unresolved set still returns 3.
            for _, target, rel, _ in resolved_changes:
                if sha(target) != expected_raw[rel] or sha(source / rel) != source_raw[rel]:
                    raise ValueError(f'Conflict changed after scan: {rel}; no files written')
            for path, target, rel, wanted in resolved_changes:
                _replace_from_source(path, target, source_raw[rel], expected_raw[rel])
                state['files'][rel] = wanted
                _write_state(state_path, state)
            raise ConflictsDetected(unresolved, adopted, resolve_conflicts)
        # All current conflicts are explicitly named. They can join ordinary pending
        # exports, which retain the normal all-files preflight before the first write.
        for path, target, rel, _ in resolved_changes:
            if sha(target) != expected_raw[rel] or sha(path) != source_raw[rel]:
                raise ValueError(f'Conflict changed after scan: {rel}; no files written')
        changes.extend(resolved_changes)
        conflicts = []
    # Identical-file adoption changes metadata only. Persist it even if unrelated
    # destination edits abort this run, so the next run has a usable baseline.
    if adopted:
        _write_state(state_path, state)
    if conflicts:
        # A diagnostic outcome, not a crash. No vault content changed; only the
        # explicitly requested baseline above may have been saved.
        raise ConflictsDetected(conflicts, adopted)
    if not apply:
        print(f'CHECK: {len(paths)} managed files, {len(changes)} pending exports, 0 conflicts. No writes.')
        return len(changes)
    destination.mkdir(parents=True, exist_ok=True)
    # Preflight every file again before the first mutation.
    for rel, before in expected.items():
        if sync_sha(contained(destination, rel)) != before:
            raise ValueError(f'Changed during preflight: {rel}; no writes performed')
    for path, target, rel, wanted in changes:
        contained(destination, rel)
        if sync_sha(target) != expected[rel]:
            raise ValueError(f'Changed during export: {rel}; prior exported files preserved')
        _replace_from_source(path, target, source_raw[rel], expected_raw[rel])
        state['files'][rel] = wanted
        # Save progress per file so an interrupted export can be resumed.
        _write_state(state_path, state)
        if resolve_conflicts is not None and rel in resolve_conflicts:
            print(f'RESOLVED APPROVED CONFLICT: {rel}')
    for path in paths:
        rel = path.relative_to(source).as_posix()
        if sync_sha(contained(destination, rel)) != sync_sha(path):
            raise ValueError(f'Post-export hash mismatch: {rel}')
        state['files'][rel] = sync_sha(path)
    _write_state(state_path, state)
    print(f'EXPORTED: {len(changes)} files; all {len(paths)} destination hashes match. Unmanaged files untouched.')
    return len(changes)


def _report_conflicts(conflicts, out_path, adopted=(), resolved=()):
    """Group conflicts by reason, print a summary, and write the full list to a file.

    Returns the exit code (3): a judgment result (collisions), distinct from a
    usage/config error (1) and clean success (0).
    """
    counts = {}
    for _, reason in conflicts:
        counts[reason] = counts.get(reason, 0) + 1
    if resolved:
        print(f'RESOLVED: {len(resolved)} explicitly approved paths were written from the repository.',
              file=sys.stderr)
        for rel in resolved:
            print(f'  RESOLVED: {rel}', file=sys.stderr)
    print(f'CONFLICTS: {len(conflicts)} unmanaged destination collisions remain; '
          + ('no vault files written.' if not resolved else
             'only listed conflicts were written; pending exports were skipped.'),
          file=sys.stderr)
    if adopted:
        print(f'  ADOPTED: {len(adopted)} identical-file hashes recorded in local state before abort.', file=sys.stderr)
    print('  grouped by reason:', file=sys.stderr)
    for reason, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f'    {n:6}  {reason}', file=sys.stderr)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            {'reasonCounts': counts,
             'conflicts': [{'path': rel, 'reason': reason} for rel, reason in conflicts],
             'adoptedIdentical': list(adopted),
             'resolvedFromRepository': list(resolved)},
            ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8')
    print(f'  full list ({len(conflicts)}): {out_path}', file=sys.stderr)
    print('  no-baseline = the tool has no manifest/state record for these; it cannot tell a real '
          'edit from an un-recorded prior sync. --adopt-identical records only matching files; '
          'it does not resolve divergent files.', file=sys.stderr)
    return 3


def main(argv=None):
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--check', action='store_true')
    action.add_argument('--apply', action='store_true')
    parser.add_argument('--vault', type=Path)
    parser.add_argument('--state', type=Path, default=None)
    parser.add_argument('--conflicts-out', type=Path, default=ROOT / '.work/obsidian-sync-conflicts.json')
    parser.add_argument('--adopt-identical', action='store_true')
    parser.add_argument('--resolve-conflicts-from', type=Path, metavar='PATHS_FILE',
                        help='--apply only: UTF-8 file with one current docs/vault-relative conflict path per line')
    args = parser.parse_args(argv)
    if args.resolve_conflicts_from is not None and not args.apply:
        parser.error('--resolve-conflicts-from requires --apply')
    try:
        state_path = args.state or default_state_path()
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f'Git metadata state path unavailable ({type(exc).__name__}); provide --state explicitly.', file=sys.stderr)
        return 1
    try:
        manifest = json.loads((ROOT / 'docs/source-manifest.json').read_text('utf-8'))
    except (OSError, ValueError) as exc:
        print(f'Manifest unavailable ({type(exc).__name__}); cannot sync.', file=sys.stderr)
        return 1
    try:
        resolution_paths = (read_conflict_paths(args.resolve_conflicts_from)
                            if args.resolve_conflicts_from is not None else None)
        export(ROOT / 'docs/vault', args.vault or Path(manifest['vault']), state_path,
               {item['path']: item['sha256'] for item in manifest['files']}, args.apply,
               args.adopt_identical, resolution_paths)
    except ConflictsDetected as detected:
        return _report_conflicts(detected.conflicts, args.conflicts_out, detected.adopted,
                                 detected.resolved)
    except (OSError, ValueError) as exc:
        print(f'Sync error ({type(exc).__name__}): {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
