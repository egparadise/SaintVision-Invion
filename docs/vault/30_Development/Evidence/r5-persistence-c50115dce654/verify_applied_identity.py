from pathlib import Path
import copy,datetime as dt,hashlib,json,sys
P=Path(__file__).resolve().parent;B=P.parent/'r5-followup-0814ec2a5432'
plan=json.loads((B/'idp-local-repair-plan.private.json').read_text());b=json.loads((B/'bindings.private.json').read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(plan['targetProfile'])==plan['candidateProfileSHA256'] and sha(plan['targetBundle'])==plan['candidateBundleSHA256']
sys.path.insert(0,str(Path(b['schedulerSource'])/'services/control-plane/src'))
from inv.identity import AccessTokens
profile=json.loads(Path(plan['targetProfile']).read_text());identity=profile['identity']
assert Path(identity['jwks_file']).resolve()==Path(plan['targetBundle']).resolve()
AccessTokens(**identity)
wrong=copy.deepcopy(identity);wrong['issuer']='https://unrelated.invalid/realms/saintvision'
try:AccessTokens(**wrong)
except ValueError:wrong_refused=True
else:raise AssertionError('Wrong issuer was accepted')
expired=P/'expired-identity-negative.private.json';body=json.loads(Path(plan['targetBundle']).read_text());body['expiresAt']=int(dt.datetime.now(dt.timezone.utc).timestamp())-1
expired.write_text(json.dumps(body),encoding='utf-8')
bad=copy.deepcopy(identity);bad['jwks_file']=str(expired)
try:AccessTokens(**bad)
except ValueError:expired_refused=True
else:raise AssertionError('Expired public policy was accepted')
assert all(sha(x['source'])==x['sourceSHA256'] and sha(Path(plan['backupDirectory'])/x['backupName'])==x['sourceSHA256'] for x in plan['backups'])
result=dict(observedAtKST=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat(),exit=0,actualNewProfileConstructed=True,wrongIssuerRefused=wrong_refused,expiredPolicyRefused=expired_refused,targetProfileSHA256=sha(plan['targetProfile']),targetBundleSHA256=sha(plan['targetBundle']),originalInputsUnchanged=5,verifiedBackups=5,tokenMinted=False,freshTokenAcceptance=False,browserAcceptance=False,serviceSwitched=False)
(P/'idp-offline-readback.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result))
