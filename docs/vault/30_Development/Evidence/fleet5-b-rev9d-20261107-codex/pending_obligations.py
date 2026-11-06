"""New machine-readable pending obligations; no model writer or runtime binding."""
import hashlib,json
from pathlib import Path
E=Path(__file__).resolve().parent
def main():
    hashes={n:hashlib.sha256((E/n).read_bytes()).hexdigest() for n in ('model.py','lifecycle.py')}
    d={'task':'FLEET5-B-REV9D-FIX-ONLY-20261107','modelLifecycleSHA256':hashes,'obligations':[
       {'id':'B9B-I3-FUTURE-TENANT-EPOCH','state':'PENDING_BEFORE_ANY_EPOCH_WRITER','currentBound':'Model tenant_execution is keyed by tenantId/epoch; control_epoch is fixed and current scope must match it; model bytes intentionally unchanged','trigger':'Any future model epoch writer or cross-epoch Node admission','requiredBeforeGrant':['Preserve tenant-wide kill-switch denial across epochs or prove equivalent tenant-wide containment','Test stopped tenant with a newly added Node under a new epoch','Keep terminal register/invoke/confirm and all-Node stop predicates current'],'actualBinding':None,'codeGrant':False,'runtimeGrant':False},
       {'id':'B9C-I3-HARNESS-FUNCTION-SCOPE-ALIASES','state':'INFO_HARNESS_ONLY_LIMITATION','path':'tests/core/test_object_store_provider_binding.py','lines':[500,514],'bound':'Module-scope exports and resolved calls are inventoried; function-scope import aliases used only for monkeypatches are not an exhaustive harness alias inventory','productionStatusUpgrade':False},
       {'id':'B9B-I4-NO-NEW-USE-SCOPE','state':'RETAINED_SCOPE_BOUND','bound':'Frozen72028 allowlists prove no new protected uses; they do not prove existing uses benign. Full receiver, parameter and universe provenance is required; graph alone is insufficient.','actualBinding':None}],
       'actualRuntimeB':0,'realBindings':None,'A1_A16':'PENDING'}
    (E/'pending-obligations.json').write_bytes((json.dumps(d,indent=2)+'\n').encode());print(json.dumps({'pendingObligations':len(d['obligations']),'modelUnchanged':True}))
if __name__=='__main__':main()
