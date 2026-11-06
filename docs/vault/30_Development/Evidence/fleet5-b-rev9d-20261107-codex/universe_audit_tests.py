"""AST source-view coverage controls; no application or mutant execution."""
import json
from pathlib import Path
import constructor_graph as cg,forwarding_discovery as fd
from source_bindings import frozen_source,sha
E=Path(__file__).resolve().parent;BA='services/control-plane/src/inv/business_auth.py'
def main():
    rows=[]
    for name,tail,expected in [
      ('operator-hidden',"\nimport operator,sys\ndef hidden():\n    return operator.attrgetter('ObservationWorker')(sys.modules['inv.observer_worker'])(object(),None)\n",True),
      ('reflective-importlib-forwarder',"\nimport importlib\ndef hidden(tenant,settings):\n    return importlib.import_module('inv.workspace_config').configured_workspace(object(),tenant,settings)\n",True),
      ('reflective-sys-forwarder',"\nimport sys\ndef hidden(tenant,settings):\n    return sys.modules['inv.workspace_config'].configured_workspace(object(),tenant,settings)\n",True),
      ('bounded-dotted-resolver',"\nimport pkgutil\ndef hidden():\n    return pkgutil.resolve_name('inv.observer_worker:ObservationWorker')(object(),None)\n",True),
      ('benign-unused-import-string',"\nimport operator\nNOTE='inv.workspace_config.configured_workspace'\n",False),
      ('benign-database-helper',"\nfrom .db import Database\ndef helper(dsn):\n    return Database(dsn)\n",False)]:
        source=frozen_source(BA)+tail;census=cg.current_census({BA:source});d,error=fd.discover(census['production'],{BA:source});assert not error
        for dataset in (census,d):assert {x['path'] for x in dataset['sourceFiles']}=={x['path'] for x in dataset['reflectionAudits']}
        audit=next(x for x in d['reflectionAudits'] if x['path']==BA);assert bool(audit['newRelevantHits']) is expected
        assert (BA in d['productionFiles']) is expected
        assert len(census['production'])==6 and len(census['harness'])==20
        rows.append({'case':name,'pass':True,'astValid':True,'sourceSHA256':sha(source),'newRelevantHits':len(audit['newRelevantHits']),'fileRetainedAsRelevant':BA in d['productionFiles'],'censusAuditedFiles':len(census['reflectionAudits']),'forwarderAuditedFiles':len(d['reflectionAudits'])})
    (E/'universe-audit-test-results.json').write_bytes((json.dumps({'executionOwner':'Codex','cases':rows,'effectfulMutantsImportedOrExecuted':False,'actualRuntimeB':0},indent=2)+'\n').encode());print(json.dumps({'universeAuditCases':len(rows),'passed':True}))
if __name__=='__main__':main()
