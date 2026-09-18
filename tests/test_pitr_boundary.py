import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import pitr_readiness as pitr

def settings(**patch):
    return dict(archive_mode='on', archive_command='copy --token=SYNTHETIC_SECRET %p /archive/%f', archive_library='', wal_level='replica') | patch

def test_command_secret_never_enters_report():
    assert 'SYNTHETIC_SECRET' not in json.dumps(pitr.assess(settings()))

def test_noop_archiver_is_not_possible():
    assert pitr.assess(settings(archive_command='/bin/true'))['verdict'] == 'absent'

def test_archive_library_is_a_configuration_candidate():
    assert pitr.assess(settings(archive_command='',archive_library='basic_archive'))['verdict']=='possible'

def test_configuration_is_not_restore_evidence():
    assert pitr.assess(settings()).get('pitrVerified') is False


def test_cli_gate_never_accepts_settings_as_recovery(monkeypatch,capsys):
    monkeypatch.setenv('TEST_PITR_DSN','SYNTHETIC_DSN_SECRET')
    monkeypatch.setattr(sys,'argv',['pitr_readiness','--dsn-env','TEST_PITR_DSN','--require-pitr','--json'])
    monkeypatch.setattr(pitr,'read_settings',lambda dsn: settings())
    assert pitr.main()==1
    output=capsys.readouterr().out
    assert 'SYNTHETIC' not in output
    assert json.loads(output)['pitrVerified'] is False

def test_connection_failure_is_redacted(monkeypatch,capsys):
    monkeypatch.setenv('TEST_PITR_DSN','SYNTHETIC_DSN_SECRET')
    monkeypatch.setattr(sys,'argv',['pitr_readiness','--dsn-env','TEST_PITR_DSN','--json'])
    def broken(dsn): raise RuntimeError('SYNTHETIC_DSN_SECRET')
    monkeypatch.setattr(pitr,'read_settings',broken)
    assert pitr.main()==2
    assert 'SYNTHETIC' not in capsys.readouterr().out

def test_both_archive_mechanisms_are_inconclusive():
    assert pitr.assess(settings(archive_library='module-secret'))['verdict']=='inconclusive'

def test_unread_library_is_not_assumed_disabled():
    report=pitr.assess(settings(archive_library=None,archive_command=''))
    assert report['verdict']=='inconclusive'


def test_unknown_values_and_extra_fields_are_not_reflected():
    report=pitr.assess(settings(archive_mode='SYNTHETIC_SECRET',wal_level='SYNTHETIC_SECRET',extra='SYNTHETIC_SECRET'))
    assert 'SYNTHETIC_SECRET' not in json.dumps(report)


def test_legacy_dsn_argument_is_not_echoed(monkeypatch,capsys):
    import pytest
    monkeypatch.setattr(sys,'argv',['pitr_readiness','--dsn','SYNTHETIC_DSN_SECRET'])
    with pytest.raises(SystemExit): pitr.main()
    output=capsys.readouterr()
    assert 'SYNTHETIC_DSN_SECRET' not in output.out+output.err

def test_read_error_does_not_poison_following_settings(monkeypatch):
    import psycopg
    seen={}
    class Connection:
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def execute(self,query,params):
            if params[0]=='archive_command':raise psycopg.errors.InsufficientPrivilege()
            return self
        def fetchone(self):return ('observed',)
    def connect(dsn,**options):seen.update(options);return Connection()
    monkeypatch.setattr(psycopg,'connect',connect)
    values=pitr.read_settings('private')
    assert values['archive_command'] is None and values['wal_level']=='observed'
    assert seen['autocommit'] is True and 'default_transaction_read_only=on' in seen['options']
