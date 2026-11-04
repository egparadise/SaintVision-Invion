"""Certificate expiry and renewal window as public console fields (Card 302).

The r3 pilot went silent when its leaves expired on 2026-10-23 and the console said only
`untrusted`, with nothing on screen about how long trust had left. These cover the projection
that fixes that, at the boundaries where an off-by-one is invisible in normal operation.

The fake row shape matches tests/core/test_lan_console.py, and the fake connection supplies
rows only -- every assertion is on what the product projects, never on the SQL it issued.
"""
from contextlib import contextmanager
from datetime import datetime,timedelta,timezone
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
import lan_console
from lan_console import RENEWAL_WINDOW_SECONDS,node_view,trust_view


def row(now,*,expires=None,enabled=True,node_id='registered-node'):
    return dict(node_id=node_id,status='online',heartbeat_at=now,received_at=now,
        endpoint='https://192.168.45.225:18443',channel_enabled=enabled,certificate_not_after=expires,
        snapshot=dict(cpuCapacityMillis=16000,cpuBusyMillis=0,memoryCapacityBytes=8000,memoryAvailableBytes=8000,osType='linux'))


def test_node_certificate_expiry_is_published_as_an_utc_stamp():
    now=datetime.now(timezone.utc)
    expires=now+timedelta(days=6)
    result=node_view(row(now,expires=expires),now)
    assert result['certificateNotAfter']==expires.astimezone(timezone.utc).isoformat()
    assert result['certificateNotAfter'].endswith('+00:00')


def test_a_non_utc_column_value_is_republished_in_utc():
    """The column is timestamptz, so a session offset must not reach the public field."""
    now=datetime.now(timezone.utc)
    expires=(now+timedelta(days=6)).astimezone(timezone(timedelta(hours=9)))
    result=node_view(row(now,expires=expires),now)
    assert result['certificateNotAfter'].endswith('+00:00')
    assert datetime.fromisoformat(result['certificateNotAfter'])==expires


def test_a_node_without_a_channel_certificate_publishes_null():
    now=datetime.now(timezone.utc)
    assert node_view(row(now,expires=None),now)['certificateNotAfter'] is None


@pytest.mark.parametrize(('offset','state','seconds'),[
    (timedelta(seconds=RENEWAL_WINDOW_SECONDS+1),'ok',RENEWAL_WINDOW_SECONDS+1),
    (timedelta(seconds=RENEWAL_WINDOW_SECONDS),'renewal-window',RENEWAL_WINDOW_SECONDS),
    (timedelta(seconds=1),'renewal-window',1),
    (timedelta(seconds=0),'expired',0),
    (timedelta(seconds=-1),'expired',0),
])
def test_window_and_expiry_boundaries(offset,state,seconds):
    """Exactly at the window start is inside it; at or past expiry never reports a negative."""
    now=datetime.now(timezone.utc)
    trust=trust_view([row(now,expires=now+offset)],now)
    assert trust['state']==state
    assert trust['secondsUntilEarliestExpiry']==seconds


def test_the_window_starts_two_days_before_the_earliest_expiry():
    now=datetime.now(timezone.utc)
    earliest=now+timedelta(days=6)
    rows=[row(now,expires=earliest+timedelta(days=1),node_id='later'),
        row(now,expires=earliest,node_id='earliest')]
    trust=trust_view(rows,now)
    assert trust['earliestCertificateNotAfter']==earliest.astimezone(timezone.utc).isoformat()
    assert datetime.fromisoformat(trust['renewalWindowStartsAt'])==earliest-timedelta(seconds=172800)
    assert RENEWAL_WINDOW_SECONDS==172800


@pytest.mark.parametrize('rows',[
    pytest.param([],id='no-nodes'),
    pytest.param('missing',id='no-channel-certificate'),
    pytest.param('disabled',id='disabled-channel-only'),
])
def test_trust_is_unknown_without_an_enabled_channel_expiry(rows):
    now=datetime.now(timezone.utc)
    if rows=='missing': rows=[row(now,expires=None)]
    elif rows=='disabled': rows=[row(now,expires=now+timedelta(days=6),enabled=False)]
    trust=trust_view(rows,now)
    assert trust=={'earliestCertificateNotAfter':None,'renewalWindowStartsAt':None,
        'secondsUntilEarliestExpiry':None,'state':'unknown'}


def test_a_disabled_channel_cannot_drag_the_earliest_expiry_down():
    """A revoked channel's stale certificate must not raise a false renewal alarm."""
    now=datetime.now(timezone.utc)
    rows=[row(now,expires=now+timedelta(seconds=10),enabled=False,node_id='revoked'),
        row(now,expires=now+timedelta(days=6),node_id='live')]
    trust=trust_view(rows,now)
    assert trust['state']=='ok'
    assert datetime.fromisoformat(trust['earliestCertificateNotAfter'])==now+timedelta(days=6)


def test_a_pending_channel_row_is_ignored_but_a_live_sibling_still_counts():
    now=datetime.now(timezone.utc)
    rows=[row(now,expires=None,node_id='enrolling'),row(now,expires=now+timedelta(seconds=1),node_id='live')]
    trust=trust_view(rows,now)
    assert trust['state']=='renewal-window' and trust['secondsUntilEarliestExpiry']==1


class _Connection:
    """Supplies rows for the statements snapshot() already issues, and records them."""

    def __init__(self,rows,now):
        self.rows=rows
        self.now=now
        self.statements=[]

    def execute(self,sql,*args):
        self.statements.append(' '.join(sql.split()))
        if 'clock_timestamp()' in sql: return _Result([dict(now=self.now)])
        if 'FROM inv.nodes' in sql: return _Result(self.rows)
        if 'kill_switch' in sql: return _Result([dict(kill_switch=False)])
        if 'FROM inv.runs' in sql: return _Result([])
        if 'FROM inv.resources' in sql: return _Result([])
        raise AssertionError('snapshot issued an unexpected statement: '+sql)


class _Result:
    def __init__(self,rows): self.rows=rows
    def fetchone(self): return self.rows[0]
    def fetchall(self): return self.rows


def _snapshot(monkeypatch,tmp_path,rows,now):
    connection=_Connection(rows,now)

    @contextmanager
    def transaction(_tenant):
        yield connection

    monkeypatch.setattr(lan_console,'load',lambda _path: dict(tenantId='t',serverIP='192.168.45.74',nodeId='registered-node'))
    monkeypatch.setattr(lan_console,'runtime',lambda _state: type('R',(),dict(transaction=staticmethod(transaction)))())
    return lan_console.snapshot(tmp_path),connection


def test_snapshot_publishes_trust_beside_the_existing_fields(monkeypatch,tmp_path):
    now=datetime.now(timezone.utc)
    earliest=now+timedelta(seconds=RENEWAL_WINDOW_SECONDS-1)
    rows=[row(now,expires=earliest,node_id='a'),row(now,expires=now+timedelta(days=6),node_id='b')]
    result,_connection=_snapshot(monkeypatch,tmp_path,rows,now)
    assert result['trust']['state']=='renewal-window'
    assert datetime.fromisoformat(result['trust']['earliestCertificateNotAfter'])==earliest
    assert [node['certificateNotAfter'] for node in result['nodes']]==[
        earliest.astimezone(timezone.utc).isoformat(),
        (now+timedelta(days=6)).astimezone(timezone.utc).isoformat()]
    # The pre-existing contract is untouched.
    for key in ('source','serverAddress','generatedAt','nodes','runs','offered','killSwitch',
            'userWorkloadSubmission','webAuthenticationConfigured','tests'):
        assert key in result,key
    assert result['source']=='live-postgresql-mtls' and result['userWorkloadSubmission'] is False


def test_snapshot_adds_no_new_statement(monkeypatch,tmp_path):
    """The card forbids new SQL: the trust fields come from columns already selected."""
    now=datetime.now(timezone.utc)
    _result,connection=_snapshot(monkeypatch,tmp_path,[row(now,expires=now+timedelta(days=6))],now)
    assert len(connection.statements)==5
    assert sum('certificate_not_after' in sql for sql in connection.statements)==1
    assert not any('not_after' in sql and 'FROM inv.nodes' not in sql for sql in connection.statements)
