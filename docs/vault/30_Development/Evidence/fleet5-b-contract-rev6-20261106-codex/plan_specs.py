"""Concrete critical-entry discovery/outer-transaction/recheck plans, proposed."""
SPECS = [
 (['_terminalize'],
  'preparation/request ID -> approval_requests run_id/project_id -> persisted run attempt, complete allocation Node IDs and resource leases; do not first lock approval then discover a new lower-rank Node',
  'terminalize caller owns outer DB transaction; BoundDatabase RunStore transition shares it; no nested commit',
  'approval request exact pending/terminal version and run version/attempt/current scope; terminal transition+approval audit atomically; no evidence-ready success shortcut'),
 (['BuildExecutionIntentQueue.enqueue'],
  'enqueue run_id -> current run/project, build admission/intent -> exact leased Node/epoch/resources; runs FOR SHARE is acquired after the full earlier-rank set',
  'enqueue caller transaction; job row/outbox commit with verified run/admission version, worker IO starts only after commit',
  'run still admitted and exact intent/admission/Node/channel current; duplicate job compare original immutable payload'),
 (['NodePrincipal.lock_current'],
  'authenticated principal Node ID+tenant -> persisted plain/B routing, inv.nodes/public.nodes and shared channel; fingerprint comes from authenticated peer, not request body',
  'request owner transaction; fixed read/lock procedure locks prefix before public.nodes; no runtime UPDATE grant for SELECT FOR UPDATE',
  'same tenant/node, non-retired public status, exact certificate fingerprint/current approved DER and epoch/C; observation lane confers no business permit'),
 (['NodeObservation.accept'],
  'authenticated Node+probe -> exact Node/shared channel, persisted probe nonce and current tuple; enumerate single affected Node before locks',
  'observation accept outer Database.transaction; nonce/probe receipt+telemetry update same transaction; signed network exchange is outside locks',
  'fresh matching probe/hash/epoch/C/cert/time, monotonic telemetry; offline->online only with no containment/retirement; never clear quarantined/draining/retired'),
 (['NodeObservation.mark_offline'],
  'MVCC enumerate online Node IDs and tenant scopes with expired heartbeat; freeze sorted complete Node set and reread after lock prefix',
  'mark_offline transaction per bounded tenant/sorted Node batch; changed discovered set aborts batch/replans without writes',
  'each remains online and heartbeat older than 60s; stronger denial preserved; only online->offline, no Node IO'),
 (['provision_channel','revoke_channel','assert_channel'],
  'exact authenticated operator Node/tenant+expected shared C; current epoch/Node row and existing channel; approved candidate DER identity independently derived before locking',
  'operator outer transaction, conn.transaction savepoint cannot shorten outer lock scope; fixed procedure owns initial prefix',
  'control and Node epoch match, expected C exact, identity/DER/expiry/endpoint trusted; initial provision vs leaf-CAS vs terminal revoke are separate; audit same C transaction, no storage-only C'),
 (['_mark_node_quarantined','_quarantine_gpu_node'],
  'causal operation/build or allocation/lease -> owned tenant/run/Node/epoch, complete retained lease set and uncertain physical receipt obligation',
  'quarantine scheduling fence + durable reconciliation/outbox transaction; physical cleanup already occurred outside; no caller success transaction can roll denial back',
  'owned same current operation/epoch, DENY-only status; never free claims, assert physical stop or success; failed safety EXECUTE leaves independent pre-IO obligation and readiness denial active'),
 (['capture_channels'],
  'model/source plan -> full candidate/member Node set and shared channel C/DER tuples, freeze sorted unique Nodes before capture',
  'model source owner transaction; guard/prefix locks complete captured channel set before plans/runs/resources; network samples outside transaction',
  'candidate membership/model hash/each Node channel tuple unchanged and enabled under locks; late member Node abort/replan'),
 (['capture_locations'],
  'model manifest -> exact location/contribution IDs -> every owner Node ID, current channel and root/policy binding; freeze complete set',
  'model commit outer transaction; Node/public/contribution/channel prefix precedes model/location/resource locks',
  'same manifest/location membership+owner consent+current channel/root/R; no catalogue row alone grants business or workload path access'),
 (['_owned_for_update'],
  'contribution ID -> tenant/registered_by_user_id/Node ID by MVCC; authenticated owner from service binding; then lock single Node/public/contribution prefix',
  'API owner activation/withdrawal transaction includes idempotency and audit; no project-grade substitute or generic OP impersonation',
  'owner+tenant+Node unchanged; revoked terminal; activation still requires Node folder confirmation and is not B admission; withdrawal preserves folder/catalogue'),
 (['set_resource_offer'],
  'capability ID -> tenant owner Node, resource kind and current offer; discover complete Node/resource/pool set before locking public Node',
  'settings API caller transaction; user/membership checks reread under named lock ranks; offer record+audit atomic',
  'authenticated live permission and capability total/unit/version/current offer unchanged; resource policy limits are not hard host quotas'),
 (['storage_view'],
  'requested storage IDs -> exact owned contribution/Node, catalogue locations and shared storage channel; explicit persisted profile selection',
  'storage read/observe transaction; prefix before contribution locks; actual storage HTTP sample outside DB transaction',
  'same owner consent/status/root/R/policy/channel/cert; read/observe never grants storage writeback or workload host path access'),
 (['reserve','_admit_locked','_reserve_short_commit','_transition','_prepare','complete','once','apply_sample','_commit_consequences'],
  'actual run/project/plan/request keys in parameters and listed query sites -> full persisted allocation/member Node IDs, public contributions/channels plus resource/claim set; for aggregate shards include ALL child Nodes, not just requester',
  'outer business caller transaction; BoundDatabase nested helpers never commit independently; resource publication/read verification prefetches immutable bytes outside locks then validates hash/version inside',
  'reread exact run attempt/version/state, project/limits/approval/plan versions, all Node current chains/status/C/root/consent, operator grant and claims/nonces; compare discovery set exactly before typed nonce/evidence/ledger commit')
]


def specialize(plan):
    matches=[]
    for suffixes,discover,owner,recheck in SPECS:
        if any(plan['function'].endswith('.'+s) for s in suffixes):
            matches.append(dict(discoverNodeResourceSet=discover,outerTransaction=owner,authoritativeRecheck=recheck))
    if matches:
        plan['concreteEntryContracts']=matches
    else:
        # Exact query sites/parameters/lock modes are function-specific in census.
        plan['concreteEntryContracts']=[dict(discoverNodeResourceSet={'parameters':plan['parameters'],'querySites':plan['discovery']['querySites']},
            outerTransaction=plan['outerTransactionOwner'],authoritativeRecheck={'tables':plan['recheck']['tables'],
            'required':'tenant scope + exact discovered primary keys/versions/status; retain original typed authorization from source, plus prefix current-chain guard when DB truth selects B'})]
    plan['requiredPrefix']=['control_epoch','tenant_controls','routing/fence','sorted transaction advisory keys',
        'sorted inv.nodes','sorted public.nodes','contributions','node_channels','role/current',
        'inv.projects','project_resource_limits','storage_budgets','shard_plans','approval_requests',
        'runs','operator_grants','named resources/claims/transfers/models/terminal','nonce/evidence/ledger/audit']
    plan['withinRankOrder']='sort qualified table name, then complete primary-key bytes; advisory keys sorted; one declared lock mode strongest required per row; no upgrades after later rank'
    plan['lateDiscovery']='abort entire transaction before any effect and replan; no savepoint continuation retaining an inverted earlier lock'
