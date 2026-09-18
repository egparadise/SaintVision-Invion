"""Read-only PITR configuration observation, never a restore acceptance certificate.

possible means configuration prerequisites only. Base backup, continuous WAL,
archive durability and recovery to a target time still require actual evidence.
Use --dsn-env ENV_NAME; connection strings and archive commands are never emitted.
--require-pitr fails closed because this tool does not verify recovery evidence.
"""
from __future__ import annotations
import argparse
import json
import os

REQUIRED = ('archive_mode', 'archive_command', 'archive_library', 'wal_level')

def assess(settings: dict[str, str | None]) -> dict:
    missing = [name for name in REQUIRED if not isinstance(settings.get(name), str)]
    def status(name):
        value = settings.get(name)
        if not isinstance(value, str): return 'unread'
        if name == 'archive_command' and value.strip().lower() in ('(disabled)','off','/bin/true','true',':','rem'): return 'disabled'
        return 'configured' if value.strip() else 'unset'
    mode = settings.get('archive_mode')
    level = settings.get('wal_level')
    safe = {'archive_mode': mode if mode in ('on','off','always') else 'unknown',
            'wal_level': level if level in ('minimal','replica','logical') else 'unknown',
            'archive_command': status('archive_command'), 'archive_library': status('archive_library')}
    report = {'verdict': 'inconclusive', 'reasons': [], 'settings': safe,
              'scope': 'configuration-only', 'pitrVerified': False,
              'requiresEvidence': ['base-backup', 'continuous-archived-wal', 'target-time-recovery', 'retention-and-media']}
    if missing:
        report['reasons'] = [name + ' could not be read' for name in missing]
        return report
    reasons = []
    if mode not in ('on','always'): reasons.append('archive_mode is not on/always')
    command = settings['archive_command'].strip()
    library = settings['archive_library'].strip()
    if command and library:
        report['reasons'] = ['archive_command and archive_library are both configured']
        return report
    if not library and command.lower() in ('','(disabled)','off','/bin/true','true',':','rem'):
        reasons.append('archive_command is empty/disabled/no-op and archive_library is unset')
    if level not in ('replica','logical'): reasons.append('wal_level is not replica/logical')
    report['verdict'] = 'absent' if reasons else 'possible'
    report['reasons'] = reasons or ['Configuration observed; WAL delivery and recovery have not been verified']
    return report

def read_settings(dsn: str) -> dict[str, str | None]:
    import psycopg
    out = {}
    with psycopg.connect(dsn, connect_timeout=10, autocommit=True,
                         options='-c default_transaction_read_only=on -c statement_timeout=3000') as conn:
        for name in REQUIRED:
            try:
                row = conn.execute('SELECT current_setting(%s, true)', (name,)).fetchone()
                out[name] = row[0] if row else None
            except psycopg.Error:
                out[name] = None
    return out

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--dsn-env', default='INV_PITR_DSN', help='Environment variable holding the libpq DSN')
    parser.add_argument('--require-pitr', action='store_true', help='Require verified recovery; settings alone always fail this gate')
    parser.add_argument('--json', action='store_true')
    args, unknown = parser.parse_known_args()
    if unknown: parser.error("Unsupported arguments; use --dsn-env ENV_NAME")
    try:
        dsn = os.environ.get(args.dsn_env)
        if not dsn: raise ValueError('Connection input unavailable')
        report = assess(read_settings(dsn))
    except Exception:
        report = assess({})
        report['reasons'] = ['Connection or settings unavailable; private diagnostics suppressed']
    if args.require_pitr:
        report['reasons'].append('PITR acceptance requires separately verified recovery evidence')
    if args.json: print(json.dumps(report, indent=2))
    else:
        print('PITR configuration: ' + report['verdict'])
        print('Recovery verified: false')
        for reason in report['reasons']: print('  - ' + reason)
    return 1 if args.require_pitr else (0 if report['verdict'] == 'possible' else 2)

if __name__ == '__main__':
    raise SystemExit(main())
