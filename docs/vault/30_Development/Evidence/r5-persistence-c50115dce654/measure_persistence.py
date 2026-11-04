from pathlib import Path
import datetime as dt,hashlib,json,subprocess,time,urllib.request
P=Path(__file__).resolve().parent
BASE=P.parent/'r5-followup-0814ec2a5432'
b=json.loads((BASE/'bindings.private.json').read_text())
def stamp():return dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat()
def parsed(v):return dt.datetime.fromisoformat(v.replace('Z','+00:00'))
samples=[]
for i in range(3):
    if i:time.sleep(8)
    with urllib.request.urlopen('http://127.0.0.1:18082/pilot/v1/overview',timeout=3) as r:
        code=r.status;v=json.load(r)
    with urllib.request.urlopen('http://127.0.0.1:3000',timeout=3) as r:web=r.status;r.read(2048)
    (P/('overview-'+str(i)+'.private.json')).write_text(json.dumps(v),encoding='utf-8')
    assert code==web==200 and v['source']=='live-postgresql-mtls'
    assert len(v['nodes'])==2 and {n['nodeId'] for n in v['nodes']}=={n['nodeId'] for n in b['nodes']}
    assert v['killSwitch'] is True and v['userWorkloadSubmission'] is False and not v['runs'] and not v['offered']
    nodes=[]
    for n in b['nodes']:
        q=next(x for x in v['nodes'] if x['nodeId']==n['nodeId'])
        assert q['status']=='online' and q['fresh'] is True
        assert -1<=(dt.datetime.now(dt.timezone.utc)-parsed(q['lastHeartbeatAt'])).total_seconds()<=120
        assert -1<=(dt.datetime.now(dt.timezone.utc)-parsed(q['lastSnapshotAt'])).total_seconds()<=120
        nodes.append(dict(alias=n['alias'],status=q['status'],fresh=q['fresh'],heartbeatAt=q['lastHeartbeatAt'],snapshotAt=q['lastSnapshotAt'],observationAgeSeconds=q['observationAgeSeconds']))
    samples.append(dict(observedAtKST=stamp(),overviewHTTP=code,webHTTP=web,nodes=nodes,runs=0,offers=0,killSwitch=True,userWorkloadSubmission=False))
for old,new in zip(samples,samples[1:]):
    for a,z in zip(old['nodes'],new['nodes']):
        assert parsed(z['heartbeatAt'])>parsed(a['heartbeatAt']) and parsed(z['snapshotAt'])>parsed(a['snapshotAt'])
assert hashlib.sha256((Path(b['statePath'])/'private-state.json').read_bytes()).hexdigest()==b['stateSHA256']
for exe,pin in b['executables'].items():assert hashlib.sha256(Path(exe).read_bytes()).hexdigest()==pin
r=subprocess.run([b['context']['git'],'-C',b['pilotSource'],'rev-parse','HEAD'],capture_output=True,check=True,timeout=10)
assert r.stdout.decode().strip()==b['pilotSourceHead']
r=subprocess.run([b['context']['git'],'-C',b['pilotSource'],'status','--porcelain','--untracked-files=no'],capture_output=True,check=True,timeout=10)
assert not r.stdout
result=dict(taskId='task_c50115dce654',terminal='term_6a916231e43b4f5acc65d986dde2726a',priorWorkerDoneMessage='msg_22ee1c05cc1d',actualNewDispatch=True,observedAtKST=stamp(),samples=samples,advancingIntervals=2,onlineFresh=2,stateBytesPreserved=True,executablesPinned=True,pilotSourceHead=b['pilotSourceHead'],pilotSourceTrackedClean=True,relaunchExecuted=False,preparationExecuted=False,idpWriteExecuted=False,taskCreationExecuted=False,rotationExecuted=False,exit=0)
(P/'http-persistence.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(exit=0,observedAtKST=result['observedAtKST'],overviewHTTP=200,webHTTP=200,onlineFresh=2,strictlyAdvancingIntervals=2,runs=0,offers=0,stateBytesPreserved=True,source03Clean=True)))
