"""One canonical numeric rank/key/mode catalog for source plans AND procedures."""
import json
from pathlib import Path

E=Path(__file__).resolve().parent
OLD=json.loads((E.parent/'fleet5-b-contract-rev5-20261106-codex/source-analysis.json').read_bytes())['rankGroups']
BASES=[0,100,200,300,400,500,600,700,800,1100,1200,1300,1400,1500,1600,1700,1800,1900,2000,2100,2200,2250,2300]
CATALOG={}
for group,base in zip(OLD,BASES):
    for index,table in enumerate(group):
        CATALOG[table]=dict(rank=base+index,key='tenant_id then complete primary-key canonical bytes; full discovered scope sorted',
            allowedModes=['FOR SHARE','FOR KEY SHARE','FOR UPDATE','FOR NO KEY UPDATE'],source='explicit inherited observed-source class')
# Every proposed B table is explicit; no coarse role/ledger bucket or implicit rank.
ROLE=[
 ('inv.node_role_routing',200,'tenant_id,node_id'),
 ('inv.node_role_cohorts',210,'tenant_id,cohort_id'),
 ('inv.node_role_service_bindings',800,'login_oid,service_id,tenant_id'),
 ('inv.node_role_authority_anchors',810,'tenant_id,node_id,epoch'),
 ('inv.node_role_lineage_anchors',820,'tenant_id,node_id,epoch,root_lineage_id'),
 ('inv.node_role_current',830,'tenant_id,node_id,epoch'),
 ('inv.node_role_denial_facts',840,'tenant_id,node_id,epoch,fact_kind,cause_operation_id'),
 ('inv.node_role_safety_obligations',850,'tenant_id,node_id,epoch,operation_id'),
 ('inv.node_role_operations',860,'tenant_id,node_id,epoch,operation_id'),
 ('inv.node_role_approvals',870,'tenant_id,node_id,epoch,root_lineage_id,approval_hash'),
 ('inv.node_role_lineage_tombstones',880,'tenant_id,node_id,epoch,root_lineage_id,ancestor_hash'),
 ('inv.node_role_candidates',890,'tenant_id,node_id,epoch,candidate_id'),
 ('inv.node_role_folder_root_observations',900,'tenant_id,node_id,epoch,contribution_id,observation_hash'),
 ('inv.node_role_storage_bindings',910,'tenant_id,node_id,epoch,contribution_id,r'),
 ('inv.node_role_member_cas',920,'tenant_id,node_id,epoch,operation_id'),
 ('inv.node_role_releases',930,'tenant_id,node_id,epoch,release_id'),
 ('inv.node_role_delegations',940,'tenant_id,node_id,epoch,delegation_id'),
 ('inv.node_role_gate_acks',950,'tenant_id,node_id,epoch,gate_id,sequence'),
 ('inv.node_role_admissions',960,'tenant_id,node_id,epoch,admission_id'),
 ('inv.node_role_leases',970,'tenant_id,node_id,epoch,lease_id'),
 ('inv.node_role_signing_intents',980,'tenant_id,node_id,epoch,intent_id'),
 ('inv.node_role_delivery_challenges',990,'tenant_id,node_id,epoch,challenge_id'),
 ('inv.node_role_key_possessions',1000,'tenant_id,node_id,epoch,challenge_id,possession_hash'),
 ('inv.node_role_delivery_consumptions',1010,'tenant_id,node_id,epoch,consumption_id'),
 ('inv.node_role_key_deliveries',1020,'tenant_id,node_id,epoch,delivery_id'),
 ('inv.node_role_request_issuance',1030,'tenant_id,node_id,epoch,request_id'),
 ('inv.node_role_safety_requests',1040,'tenant_id,node_id,epoch,safety_request_id'),
 ('inv.node_role_reconcile_evidence',1050,'tenant_id,node_id,epoch,operation_id,evidence_hash'),
 ('inv.node_role_activation_ledger',2320,'tenant_id,node_id,epoch,activation_ledger_id'),
 ('inv.node_role_request_commits',2330,'tenant_id,node_id,epoch,request_id'),
 ('inv.node_role_revocation_outbox',2340,'tenant_id,node_id,epoch,root_lineage_id,outbox_id'),
]
for table,rank,key in ROLE:
    CATALOG[table]=dict(rank=rank,key=key+' sorted canonical bytes over complete discovered set',
        allowedModes=['FOR SHARE','FOR UPDATE'],source='explicit Rev6 proposed contract')
CATALOG['@transaction_advisory']=dict(rank=300,key='sorted complete transaction advisory keys',allowedModes=['TRANSACTION_ADVISORY'],source='transaction only; online SESSION advisory rejected')
for table,rank in [('inv.node_stop_receipts',2301),('inv.result_commitments',2260),
 ('inv.result_completions',2302),('inv.shard_completions',2303),('inv.storage_sample_consumptions',2304),
 ('public.storage_checks',2305),('inv.node_channel_audit',2306)]:
    CATALOG[table]=dict(rank=rank,key='tenant_id then complete immutable operation/receipt primary key sorted canonical bytes',allowedModes=['FOR SHARE','FOR UPDATE'],source='explicit original atomic receipt/evidence class')
RANK={k:v['rank'] for k,v in CATALOG.items()}
RANK_GROUPS=[[k for k,v in CATALOG.items() if v['rank']==rank] for rank in sorted(set(RANK.values()))]
PREFIX=['inv.control_epoch','inv.tenant_controls','inv.node_role_routing','inv.node_role_cohorts',
        '@transaction_advisory','inv.nodes','public.nodes','public.storage_contributions','inv.node_channels',
        'inv.node_role_service_bindings','inv.node_role_authority_anchors','inv.node_role_lineage_anchors']


def locks(tables,write=()):
    result=[]
    for table in sorted(set(tables),key=lambda t:(RANK.get(t,99999),t)):
        if table not in CATALOG:raise ValueError('UNKNOWN_LOCKED_TABLE_BLOCK:'+table)
        result.append(dict(table=table,**CATALOG[table],mode='TRANSACTION_ADVISORY' if table.startswith('@') else 'FOR UPDATE' if table in write else 'FOR SHARE'))
    return result


def procedure_locks(name,effects):
    tables=set(PREFIX)|set(effects)
    write={t for t,e in effects.items() if e['verb'] in ('UPDATE','INSERT','INSERT_OR_UPDATE','INSERT_OR_APPEND')}
    # All new child insertion/absence decisions serialize through SAME anchor,
    # including reader/admission vs registration, signer publication vs revoke.
    if any(t.startswith('inv.node_role_') for t in effects):write|={'inv.node_role_authority_anchors','inv.node_role_lineage_anchors'}
    tables|={'inv.node_role_current','inv.node_role_denial_facts','inv.node_role_safety_obligations'}
    if any(s in name for s in ('approval','lineage','sign','release','delegation','activation','delivery','issuance','refresh')):
        tables|={'inv.node_role_approvals','inv.node_role_lineage_tombstones','inv.operator_grants'}
    if any(s in name for s in ('evidence','receipt','outcome','obligation')):
        tables|={'inv.runs','inv.resource_leases','inv.tool_claims','inv.evidence','inv.outbox'}
    if name.startswith(('b_lock_','b_register_io','b_confirm_','b_mark_io','b_settle_')):
        write|={'inv.node_role_authority_anchors','inv.node_role_lineage_anchors'}
    if 'execution_stop' in name:tables|={'inv.node_stop_receipts'}
    if 'result_completion' in name:tables|={'inv.result_commitments','inv.result_completions'}
    if 'shard_completion' in name:tables|={'inv.shard_completions'}
    if 'storage_sample' in name:tables|={'public.storage_checks','inv.storage_sample_consumptions'}
    if any(s in name for s in ('result_completion','shard_completion')):tables|={'inv.shard_plans','inv.approval_requests'}
    return locks(tables,write)


def check(matrix):
    errors=[]
    for table in matrix['tables']:
        if table not in CATALOG:errors.append('UNRANKED:'+table)
    for proc,p in matrix['procedures'].items():
        actual=p.get('lockList',[])
        if actual!=procedure_locks(proc,p['effects']):errors.append('LOCK_LIST:'+proc)
    for anchor in ('inv.node_role_authority_anchors','inv.node_role_lineage_anchors'):
        if RANK[anchor]>=RANK['inv.node_role_lineage_tombstones']:errors.append('ANCHOR_AFTER_CHILD')
    return errors
