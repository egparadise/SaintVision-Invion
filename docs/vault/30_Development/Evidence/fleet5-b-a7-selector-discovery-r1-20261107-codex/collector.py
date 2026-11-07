"""Target-derived A7 selector inventory. Source/AST data only, no product import.

Git grep -E is the selector engine in every mode, retaining the original ERE
semantics. Filesystem enumeration supplies its inputs independently of BASE.
"""
import ast
import hashlib
import os
from pathlib import Path, PurePosixPath
import subprocess

ROOTS = ('services/control-plane/src', 'src', 'tools')
SELECTOR = r'NodeDelivery|DeliveryWorker|DeliveryAttempt|DeliveryQueue|node_transport|from[[:space:]].*dispatch|import[[:space:]].*dispatch|\.deliver\b'


class Unresolved(Exception):
    def __init__(self, reason, detail):
        self.reason, self.detail = reason, detail
        super().__init__(reason + ': ' + str(detail))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def safe(path):
    p = PurePosixPath(path)
    if p.is_absolute() or any(x in ('.', '..') for x in p.parts) or any(x in path for x in ('\\', '\n', '\r', '\x00', ':')):
        raise Unresolved('UNSUPPORTED_PATH', path)
    if not path.endswith('.py') or not any(path.startswith(root + '/') for root in ROOTS):
        raise Unresolved('PATH_OUTSIDE_SELECTOR_ROOTS', path)
    return path


def run(cwd, argv, receipts, accepted=(0,)):
    result = subprocess.run(argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    receipts.append({'argv': argv, 'exit': result.returncode, 'stdoutSHA256': sha(result.stdout),
                     'stderrSHA256': sha(result.stderr), 'stderrUTF8': result.stderr.decode('utf8', errors='replace')})
    if result.returncode not in accepted:
        raise Unresolved('TARGET_ENUMERATION_OR_READ_FAILED', receipts[-1])
    return result.stdout


def decode(data, path):
    try:
        return data.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise Unresolved('SOURCE_ENCODING_UNRESOLVED', {'path': path, 'error': str(exc)}) from exc


def nul_paths(data):
    try:
        return [v for v in data.decode('utf8').split('\0') if v]
    except UnicodeDecodeError as exc:
        raise Unresolved('PATH_ENCODING_UNRESOLVED', str(exc)) from exc


def enumerate_filesystem(root):
    """Enumerate actual .py files, including untracked/ignored files, not HEAD."""
    result = []

    def visit(directory):
        try:
            entries = sorted(os.scandir(directory), key=lambda e: e.name)
            for entry in entries:
                path = Path(entry.path)
                if entry.is_symlink():
                    raise Unresolved('SYMLINK_TARGET_UNSUPPORTED', path.relative_to(root).as_posix())
                if entry.is_dir(follow_symlinks=False):
                    visit(path)
                elif entry.is_file(follow_symlinks=False) and path.suffix == '.py':
                    result.append(safe(path.relative_to(root).as_posix()))
        except OSError as exc:
            raise Unresolved('TARGET_ENUMERATION_OR_READ_FAILED', str(exc)) from exc

    for relative in ROOTS:
        path = root / relative
        if path.is_symlink() or not path.is_dir():
            raise Unresolved('SELECTOR_ROOT_UNAVAILABLE', relative)
        visit(path)
    return sorted(result)


def read_filesystem(root, paths):
    data, stamps = {}, {}
    for relative in paths:
        path = root / relative
        try:
            before = path.lstat()
            if path.is_symlink() or not path.is_file():
                raise Unresolved('UNSUPPORTED_SOURCE_FILE', relative)
            raw = path.read_bytes()
            after = path.lstat()
        except OSError as exc:
            raise Unresolved('TARGET_ENUMERATION_OR_READ_FAILED', {'path': relative, 'error': str(exc)}) from exc
        stamp = lambda st: (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns)
        if stamp(before) != stamp(after):
            raise Unresolved('WORKING_TARGET_CHANGED_DURING_READ', relative)
        decode(raw, relative)
        data[relative], stamps[relative] = raw, stamp(after)
    return data, stamps


def collect(root, kind, ref=None):
    """Normal discovery/read entrypoint; no caller-supplied path set/world."""
    root = Path(root).resolve(strict=True)
    receipts, membership, object_ids = [], {}, {}
    resolved = None
    if kind == 'commit':
        if not ref:
            raise Unresolved('COMMIT_REF_REQUIRED', None)
        resolved = run(root, ['git', 'rev-parse', '--verify', ref + '^{commit}'], receipts).decode('ascii').strip()
        tree = run(root, ['git', 'ls-tree', '-r', '-z', resolved, '--', *ROOTS], receipts)
        all_paths = []
        for item in tree.split(b'\0'):
            if not item:
                continue
            header, rawpath = item.split(b'\t', 1)
            path = nul_paths(rawpath)[0]
            if not path.endswith('.py'):
                continue
            safe(path)
            mode, typ, oid = header.decode('ascii').split()
            if mode not in ('100644', '100755') or typ != 'blob':
                raise Unresolved('UNSUPPORTED_GIT_TREE_ENTRY', {'path': path, 'mode': mode, 'type': typ})
            all_paths.append(path)
            membership[path], object_ids[path] = 'TRACKED_IN_TARGET_COMMIT', oid
        selected_raw = run(root, ['git', 'grep', '-l', '-z', '-E', SELECTOR, resolved, '--', *ROOTS], receipts, (0, 1))
        selected = []
        for item in nul_paths(selected_raw):
            prefix = resolved + ':'
            if not item.startswith(prefix):
                raise Unresolved('UNEXPECTED_GIT_GREP_PATH', item)
            path = item[len(prefix):]
            if path.endswith('.py'):
                selected.append(safe(path))
        world = {}
        for path in sorted(set(selected)):
            if path not in object_ids:
                raise Unresolved('SELECTED_PATH_NOT_IN_TARGET_TREE', path)
            world[path] = run(root, ['git', 'cat-file', 'blob', object_ids[path]], receipts)
    elif kind in ('working', 'filesystem-fixture'):
        all_paths = enumerate_filesystem(root)
        before, stamps = read_filesystem(root, all_paths)
        if kind == 'working':
            resolved = run(root, ['git', 'rev-parse', 'HEAD'], receipts).decode('ascii').strip()
            tracked = set(nul_paths(run(root, ['git', 'ls-files', '--cached', '-z', '--', *ROOTS], receipts)))
            membership = {path: 'TRACKED_IN_INDEX' if path in tracked else 'UNTRACKED_INCLUDING_IGNORED' for path in all_paths}
        else:
            membership = {path: 'NOT_A_GIT_TREE_FILESYSTEM_FIXTURE' for path in all_paths}
        selected = []
        # Bounded literal path chunks avoid the Windows command-line length limit.
        # --no-exclude-standard keeps physically present untracked/ignored .py.
        for offset in range(0, len(all_paths), 48):
            out = run(root, ['git', '--literal-pathspecs', 'grep', '--no-index', '--no-exclude-standard',
                            '-l', '-z', '-E', SELECTOR, '--', *all_paths[offset:offset + 48]], receipts, (0, 1))
            for path in nul_paths(out):
                path = safe(path.removeprefix('./'))
                if path not in before:
                    raise Unresolved('SELECTED_PATH_NOT_ENUMERATED', path)
                selected.append(path)
        if enumerate_filesystem(root) != all_paths:
            raise Unresolved('WORKING_PATH_SET_CHANGED_DURING_DISCOVERY', None)
        after, after_stamps = read_filesystem(root, all_paths)
        if before != after or stamps != after_stamps:
            raise Unresolved('WORKING_TARGET_CHANGED_DURING_DISCOVERY', None)
        world = {path: after[path] for path in sorted(set(selected))}
    else:
        raise Unresolved('UNSUPPORTED_TARGET_KIND', kind)
    inventory = []
    for path, raw in sorted(world.items()):
        source = decode(raw, path)
        try:
            ast.parse(source, path)
        except SyntaxError as exc:
            raise Unresolved('SELECTED_SOURCE_PARSE_UNRESOLVED', {'path': path, 'error': str(exc)}) from exc
        inventory.append({'path': path, 'bytes': len(raw), 'rawSHA256': sha(raw), 'decodedTextSHA256': sha(source.encode()),
                          'membership': membership[path], 'gitBlobID': object_ids.get(path), 'ASTParseOnly': True})
    report = {'targetKind': kind, 'requestedRef': ref, 'resolvedTargetCommitOrWorkingHEAD': resolved,
              'root': str(root), 'selector': SELECTOR, 'selectorEngine': 'git grep -E (original POSIX ERE, no Python regex translation)',
              'productionRoots': list(ROOTS), 'enumeratedProductionPythonCount': len(all_paths),
              'selectedCount': len(world), 'selectedInventory': inventory, 'queryReceipts': receipts,
              'pathsDerivedFromEvaluatedTarget': True, 'baseWorldUsedForDiscovery': False,
              'filesystemFixtureIsGitCommit': False if kind == 'filesystem-fixture' else None,
              'workingModel': 'No symlinks; read/encoding failures unresolved. Filesystem paths/content/stamps rechecked around selector; not an atomic hostile-filesystem/runtime proof.',
              'productOrMutantRuntimeExecuted': False}
    return world, report
