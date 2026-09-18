"""Restore a pinned retained pilot backup into a new disposable Docker cluster.

No ambient admin/runtime DSN is used. Source roles are provisioned as NOLOGIN;
only a new random test login is used. This does not test PITR or off-device media.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys
import time
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from sqlalchemy.engine import URL

from rehearse_lan_upgrade import read_snapshot, read_backup_file, digest_db, assert_preserved
from saintvision.storage.readroot import ReadRoot
from recovery_drill import Postgres, _definer_verdict
from migration_graph import chain

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP_ROLES = ('inv_app', 'inv_kernel', 'inv_lan_runtime')


class RehearsalFailure(Exception):
    def __init__(self, report):
        self.report = report


def _missing_container(result):
    return result.returncode != 0 and "no such object" in (result.stderr or "").lower()


def _cleanup_owned(name, report):
    """Record cleanup independently; never replace the body report."""
    cleanup = {"status": "query-error", "container": name}
    try:
        inspected = docker('inspect', '--format', '{{index .Config.Labels "ai.saintvision.restore"}}', name, check=False)
    except Exception as error:
        cleanup.update(errorType=type(error).__name__, detail="ownership query failed")
        report["cleanup"] = cleanup
        return
    if inspected.returncode != 0:
        cleanup["status"] = "confirmed-absent" if _missing_container(inspected) else "query-error"
        report["cleanup"] = cleanup
        return
    if inspected.stdout.strip() != name:
        cleanup.update(status="ownership-mismatch", detail="container preserved")
        report["cleanup"] = cleanup
        return
    try:
        removed = docker('rm', '-f', name, check=False)
    except Exception as error:
        cleanup.update(status="remove-error", errorType=type(error).__name__, detail="remove failed")
        report["cleanup"] = cleanup
        return
    if removed.returncode != 0:
        cleanup.update(status="remove-error", detail="remove failed")
        report["cleanup"] = cleanup
        return
    try:
        verified = docker('inspect', '--format', '{{index .Config.Labels "ai.saintvision.restore"}}', name, check=False)
    except Exception as error:
        cleanup.update(status="query-error", errorType=type(error).__name__, detail="post-remove query failed")
        report["cleanup"] = cleanup
        return
    if _missing_container(verified):
        cleanup["status"] = "confirmed-removed"
    elif verified.returncode == 0:
        cleanup.update(status="remove-error", detail="container still present after remove")
    else:
        cleanup.update(status="query-error", detail="post-remove ownership unknown")
    report["cleanup"] = cleanup


def pinned_snapshot(directory, expected_hash):
    if not re.fullmatch('[0-9a-f]{64}', expected_hash):
        raise ValueError('Pinned archive SHA256 required')
    directory = Path(os.path.abspath(directory))
    for parent in (directory, *directory.parents):
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('Backup ancestor must be a real directory')
    for filename, limit in [('manifest.json', 8 * 1024 * 1024), ('snapshot.dump', 256 * 1024 * 1024)]:
        info = (directory / filename).lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or getattr(info, 'st_file_attributes', 0) & 0x400 or info.st_size > limit:
            raise ValueError('Bounded regular single-link backup required')
    root = ReadRoot(directory)
    manifest = json.loads(read_backup_file(root, 'manifest.json'))
    if manifest['archiveSha256'] != expected_hash:
        raise ValueError('Saved manifest differs from pinned archive')
    return read_snapshot(directory, manifest, root=root), manifest


def docker(*args, env=None, check=True):
    result = subprocess.run(['docker', *map(str, args)], env=env, capture_output=True, text=True, timeout=120)
    if check and result.returncode:
        raise RuntimeError('Owned Docker operation failed; private diagnostics suppressed')
    return result


def rehearse(directory, expected_hash, image):
    archive, manifest = pinned_snapshot(directory, expected_hash)
    resolved_image = docker('image', 'inspect', '--format', '{{.Id}}', image).stdout.strip()
    if not re.fullmatch('sha256:[0-9a-f]{64}', resolved_image):
        raise ValueError('Local content-addressed PostgreSQL image required')
    name = 'sv-independent-restore-' + uuid4().hex
    password = secrets.token_urlsafe(32)
    login, login_password = 'restore_' + uuid4().hex, secrets.token_urlsafe(32)
    report = dict(startedAt=datetime.now(timezone.utc).isoformat(),
                  codeSHA=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  worktreeDirty=bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT)),
                  pythonVersion=sys.version.split()[0],
                  scope='independent-disposable-cluster-retained-backup-restore',
                  archiveSha256=expected_hash, archiveBytes=len(archive),
                  postgresImage=resolved_image, bootstrapRoles=list(BOOTSTRAP_ROLES),
                  operationalAcceptanceAssessed=False, sourceDatabaseContacted=False,
                  originalCredentialsReused=False, offDeviceBackup=False, pointInTimeRecovery=False)
    inputs = [Path(__file__).resolve(), *[ROOT / 'tools' / path for path in (
        'rehearse_lan_upgrade.py', 'migration_graph.py', 'recovery_drill.py',
        'check_definer_functions.py', 'definer-policy.json')],
        *sorted((ROOT / 'migrations').rglob('*.py')),
        ROOT / 'src/saintvision/db/migration_guard.py',
        ROOT / 'src/saintvision/storage/readroot.py',
        ROOT / 'services/control-plane/src/inv/db.py']
    report['sourceHashes'] = {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                              for path in inputs}
    stage = 'create-owned-cluster'
    try:
        docker('run', '-d', '--name', name, '--label', 'ai.saintvision.restore=' + name,
               '--memory', '768m', '--cpus', '1', '--pids-limit', '256',
               '--tmpfs', '/var/lib/postgresql/data:rw,size=536870912',
               '--publish', '127.0.0.1::5432', '--env', 'POSTGRES_PASSWORD',
               '--env', 'POSTGRES_DB=restore_snapshot', resolved_image,
               env={**os.environ, 'POSTGRES_PASSWORD': password})
        port = json.loads(docker('inspect', '--format', '{{json .NetworkSettings.Ports}}', name).stdout)['5432/tcp'][0]['HostPort']
        owner = make_conninfo(host='127.0.0.1', port=port, user='postgres', password=password,
                             dbname='restore_snapshot', connect_timeout=2)
        for _ in range(100):
            try:
                with psycopg.connect(owner) as conn:
                    conn.execute('SELECT 1')
                break
            except psycopg.OperationalError:
                time.sleep(.1)
        else:
            raise RuntimeError('Owned restore database unavailable')
        stage = 'bootstrap-no-login-roles'
        with psycopg.connect(owner) as conn:
            for role in BOOTSTRAP_ROLES:
                conn.execute(sql.SQL('CREATE ROLE {} NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION').format(sql.Identifier(role)))
            conn.execute(sql.SQL('CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION').format(sql.Identifier(login), sql.Literal(login_password)))
            conn.execute(sql.SQL('GRANT inv_kernel TO {}').format(sql.Identifier(login)))
        inside = make_conninfo(owner, port=5432)
        stage = 'restore-pinned-archive'
        restored = Postgres(name).run('pg_restore', ['--dbname', inside, '--single-transaction', '--exit-on-error'], stdin=archive)
        if restored.returncode:
            # Role names are not inferred from arbitrary SQL or credentials.
            # Unknown source-role dependencies require explicit reconciliation.
            raise RuntimeError('Independent archive restore failed; reconcile declared role dependencies')
        stage = 'compare-restored-inventory'
        columns, before = digest_db(owner)
        if columns != manifest['columns'] or before != manifest['sourceInventory']:
            raise ValueError('Independent restored inventory differs from retained snapshot')
        report.update(independentClusterRestore=True, restoreExactRows=True,
                      sourceTables=len(before), sourceRows=sum(row['rows'] for row in before.values()))
        url = URL.create('postgresql+psycopg', username='postgres', password=password,
                         host='127.0.0.1', port=int(port), database='restore_snapshot')
        environment = {**os.environ, 'INV_MIGRATION_DSN': url.render_as_string(hide_password=False)}
        environment.pop('INV_DATABASE_URL', None)
        first = None
        stage = 'upgrade-and-replay'
        for _ in range(2):
            applied = subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], cwd=ROOT,
                                     env=environment, capture_output=True, timeout=180)
            if applied.returncode:
                raise RuntimeError('Independent restored migration failed; diagnostics suppressed')
            current = digest_db(owner)
            if first is not None and current != first:
                raise ValueError('Migration replay changed stored rows')
            first = current
        _, projection = digest_db(owner, columns)
        assert_preserved(before, projection, upgraded=True)
        with psycopg.connect(owner) as conn:
            heads = [row[0] for row in conn.execute('SELECT version_num FROM public.alembic_version')]
            unsafe = conn.execute('SELECT count(*) FROM pg_roles WHERE rolname=ANY(%s) AND (rolcanlogin OR rolsuper OR rolbypassrls OR rolcreatedb OR rolcreaterole OR rolreplication)', (list(BOOTSTRAP_ROLES),)).fetchone()[0]
        if heads != [chain()[-1].revision] or unsafe:
            raise ValueError('Restored schema or permission groups differ')
        stage = 'privileged-function-and-runtime-verification'
        verdict = _definer_verdict(owner)
        if not verdict.get('checked') or verdict.get('unsafe') != 0:
            raise ValueError('Independent restored privileged functions require review')
        from inv.db import Database
        runtime = make_conninfo(owner, user=login, password=login_password)
        with Database(runtime, recovery_epoch=manifest['recoveryEpoch']).transaction(manifest['tenantId']) as conn:
            nodes = conn.execute('SELECT count(*) AS n FROM inv.nodes').fetchone()['n']
            if nodes < 1:
                raise ValueError('Restored runtime cannot observe its recorded Node')
        with psycopg.connect(runtime) as conn:
            conn.execute("SELECT set_config('inv.tenant_id',%s,true)", (str(uuid4()),))
            if conn.execute('SELECT count(*) FROM inv.nodes').fetchone()[0] != 0:
                raise ValueError('Restored tenant isolation failed')
        # Read back the retained files after the entire drill, without rewriting.
        verified_archive, verified_manifest = pinned_snapshot(directory, expected_hash)
        if verified_archive != archive or verified_manifest != manifest:
            raise ValueError('Source backup changed during rehearsal')
        report.update(status='passed', finalHeads=heads, oldColumnRowsPreserved=True, replayExactRows=True,
                      permissionGroupsSafe=True, definer=verdict, runtimeTransactionPassed=True,
                      differentTenantNodesVisible=0, sourceBackupUnchanged=True,
                      completedAt=datetime.now(timezone.utc).isoformat())
        return report
    except Exception as error:
        report.update(status='failed', failedStage=stage, errorType=type(error).__name__)
        raise RehearsalFailure(report) from None
    finally:
        _cleanup_owned(name, report)
        report['disposableClusterRemoved'] = report.get('cleanup', {}).get('status') == 'confirmed-removed'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup', type=Path, required=True)
    parser.add_argument('--expected-sha256', required=True)
    parser.add_argument('--image', default='postgres:16')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Use a new report file; existing evidence is preserved')
    try:
        result = rehearse(args.backup, args.expected_sha256, args.image)
    except RehearsalFailure as error:
        with args.output.open('x', encoding='utf-8') as stream:
            json.dump(error.report, stream, indent=2)
            stream.write('\n')
        print('Independent restore failed; sanitized stage and cleanup evidence recorded.', file=sys.stderr)
        return 2
    except Exception:
        print('Independent restore failed; operating database was not contacted.', file=sys.stderr)
        return 2
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print('PASS: independent cluster restore, upgrade/replay, role isolation and runtime DB access')
    return 0 if result.get('cleanup', {}).get('status') in {'confirmed-removed', 'confirmed-absent'} else 2


if __name__ == '__main__':
    raise SystemExit(main())
