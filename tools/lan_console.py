"""Read-only operator console for the explicitly configured LAN pilot.

Loopback only. It exposes current observations and bounded acceptance results,
never credentials, arbitrary files, signing, workload mutations or fake inventory.
"""
import argparse
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import ipaddress
import json
from pathlib import Path
from urllib.parse import urlsplit
from lan_pilot import load,runtime


def node_view(row,now):
    stamp=row.get('received_at')
    age=(now-stamp).total_seconds() if stamp else None
    trusted=row.get('channel_enabled') is True and row.get('certificate_not_after') is not None and row['certificate_not_after']>now
    fresh=age is not None and 0<=age<=20 and trusted
    status=row['status']
    if not trusted: status='untrusted'
    elif not fresh: status='offline' if age is None or age>60 else 'stale'
    snap=row.get('snapshot') or {}
    cpu=snap.get('cpuCapacityMillis') if fresh else None
    busy=snap.get('cpuBusyMillis') if fresh else None
    memory=snap.get('memoryCapacityBytes') if fresh else None
    available=snap.get('memoryAvailableBytes') if fresh else None
    return dict(nodeId=row['node_id'],address=urlsplit(row.get('endpoint') or '').hostname,
        status=status,fresh=fresh,lastHeartbeatAt=row['heartbeat_at'].isoformat() if row.get('heartbeat_at') else None,
        lastSnapshotAt=stamp.isoformat() if stamp else None,observationAgeSeconds=round(age,1) if age is not None else None,
        osType=snap.get('osType'),profileVersion=snap.get('profileVersion'),agentVersion=snap.get('agentVersion'),
        cpuCores=cpu/1000 if cpu is not None else None,
        cpuUsagePercent=round(busy/cpu*100,1) if cpu and busy is not None else None,
        memoryTotalBytes=memory,memoryUsedBytes=memory-available if memory is not None and available is not None else None,
        gpuCount=None,storageTotalBytes=None,measurementScope='node-visible-linux-environment')


def acceptance_view(path,node_id):
    if not path.exists(): return []
    report=json.loads(path.read_text())
    if report.get('nodeId')!=node_id or report.get('scope')!='node-component-acceptance':
        raise ValueError('Acceptance report scope differs')
    results=[]
    for item in report.get('tests',[])[:20]:
        receipt=item.get('receipt') or {}
        results.append(dict(test=item['test'],passed=item['passed'],completedAt=item['completedAt'],
            commandId=receipt.get('commandId',item.get('commandId')),exitCode=receipt.get('exitCode'),
            stopped=receipt.get('stopped'),processStarted=receipt.get('processStarted'),reason=receipt.get('reason'),
            outputSha256=item.get('outputSha256'),stdout=item.get('stdout','')[:4000],stderr=item.get('stderr','')[:4000],
            duplicate=item.get('duplicate'),sameReceipt=item.get('sameReceipt')))
    return results


def snapshot(path):
    state=load(path)
    with runtime(state).transaction(state['tenantId']) as conn:
        now=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        rows=conn.execute('''SELECT n.node_id,n.status,n.heartbeat_at,s.received_at,s.snapshot,c.endpoint,c.enabled AS channel_enabled,c.certificate_not_after
            FROM inv.nodes n LEFT JOIN inv.node_channels c ON (c.tenant_id,c.node_id)=(n.tenant_id,n.node_id) AND c.recovery_epoch=n.recovery_epoch
            LEFT JOIN inv.node_resource_snapshots s ON (s.tenant_id,s.node_id)=(n.tenant_id,n.node_id) AND s.recovery_epoch=n.recovery_epoch AND s.channel_version=c.version
            ORDER BY n.node_id LIMIT 100''').fetchall()
        gate=conn.execute('SELECT kill_switch FROM inv.tenant_controls').fetchone()['kill_switch']
        runs=conn.execute('SELECT run_id,state,version FROM inv.runs ORDER BY run_id DESC LIMIT 30').fetchall()
        resources=conn.execute('SELECT kind,sum(offered) AS offered FROM inv.resources GROUP BY kind').fetchall()
    return dict(source='live-postgresql-mtls',serverAddress=state['serverIP'],generatedAt=now.isoformat(),
        nodes=[node_view(row,now) for row in rows],runs=[dict(runId=r['run_id'],state=r['state'],version=r['version']) for r in runs],
        offered={r['kind']:r['offered'] for r in resources},killSwitch=gate,
        userWorkloadSubmission=False,webAuthenticationConfigured=False,
        tests=acceptance_view(path/'acceptance-report.json',state['nodeId']))


def serve(path,port):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if not ipaddress.ip_address(self.client_address[0]).is_loopback:
                self.send_error(403)
                return
            if self.path!='/pilot/v1/overview':
                self.send_error(404)
                return
            try:
                data=snapshot(path)
                code=200
            except Exception:
                data=dict(error='관측 서버에서 실제 상태를 읽지 못했습니다. 연결을 확인해 주세요.')
                code=503
            raw=json.dumps(data,ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Length',str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        def log_message(self,*args): pass
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    server.daemon_threads=True
    print(json.dumps(dict(service='lan-console-read-only',port=port)),flush=True)
    server.serve_forever()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state',type=Path,required=True)
    parser.add_argument('--port',type=int,default=18082)
    parser.add_argument('--once',action='store_true')
    args=parser.parse_args()
    if args.once: print(json.dumps(snapshot(args.state),ensure_ascii=False))
    else: serve(args.state,args.port)
