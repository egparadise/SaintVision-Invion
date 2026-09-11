from datetime import datetime,timedelta,timezone
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
from lan_console import node_view,acceptance_view


def row(now):
    return dict(node_id='registered-node',status='online',heartbeat_at=now,received_at=now,
        endpoint='https://192.168.45.225:18443',channel_enabled=True,certificate_not_after=now+timedelta(days=1),
        snapshot=dict(cpuCapacityMillis=16000,cpuBusyMillis=0,memoryCapacityBytes=8000,memoryAvailableBytes=8000,osType='linux'))


def test_actual_zero_usage_and_missing_devices_are_not_replaced_with_defaults():
    now=datetime.now(timezone.utc)
    result=node_view(row(now),now)
    assert result['cpuCores']==16 and result['cpuUsagePercent']==0 and result['memoryUsedBytes']==0
    assert result['gpuCount'] is None and result['storageTotalBytes'] is None
    assert result['address']=='192.168.45.225'


@pytest.mark.parametrize('seconds,status',[(21,'stale'),(61,'offline')])
def test_stale_snapshot_is_excluded_from_available_capacity(seconds,status):
    now=datetime.now(timezone.utc)
    result=node_view(row(now-timedelta(seconds=seconds)),now)
    assert result['status']==status and not result['fresh']
    assert result['cpuCores'] is None and result['memoryTotalBytes'] is None


@pytest.mark.parametrize('fault',['revoked','expired','missing'])
def test_current_channel_authority_is_required_for_online_metrics(fault):
    now=datetime.now(timezone.utc)
    record=row(now)
    if fault=='revoked': record['channel_enabled']=False
    elif fault=='expired': record['certificate_not_after']=now-timedelta(seconds=1)
    else: record['certificate_not_after']=None
    result=node_view(record,now)
    assert result['status']=='untrusted' and result['cpuCores'] is None


def test_no_acceptance_file_means_no_synthetic_runs(tmp_path):
    assert acceptance_view(tmp_path/'absent.json','node')==[]
