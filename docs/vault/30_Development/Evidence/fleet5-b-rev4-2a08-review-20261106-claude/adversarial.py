"""Reviewer (Claude) adversarial probes against the owner's Rev4 SYMBOLIC model.

Imports owner model.py/fixtures.py/authority.py by path (fixtures.main is NOT
called, so nothing in the owner Evidence directory is written). Each probe states
the behaviour the CONTRACT requires and the model's actual answer. SYMBOLIC only:
no real keys, crypto, PG, Node or time source.
Usage: python -B adversarial.py -> adversarial-result.json next to itself.
"""
from copy import deepcopy
from pathlib import Path
import json
import sys

HERE = Path(__file__).resolve().parent
OWNER = HERE.parent / 'fleet5-b-contract-rev4-20261106-codex'
sys.path.insert(0, str(OWNER))
import fixtures as F  # noqa: E402  (definitions only)
from model import *  # noqa: E402,F401,F403
from authority import build as authority_build, valid_matrix  # noqa: E402

PROBES = []


def probe(pid, requirement, actual, contract_expects):
    PROBES.append({'id': pid, 'requirement': requirement, 'actual': actual, 'contractExpects': contract_expects, 'agreesWithContract': actual == contract_expects})


def switch_until_arm(s, m):
    old = {k: s['current'][k] for k in ('approval', 'release', 'delegation')}
    s['switchPending'] = True
    ia = node_command(s, old, command(s, old, 'INVALIDATE_EXACT_GATE')); assert ia and record_ack(s, ia)
    ack = node_command(s, m, command(s, m, 'ARM_EXACT_RELEASE')); assert ack and record_ack(s, ack)
    return ack


def deliver(s):
    ch = delivery_challenge(s); assert ch
    rc = consume_possession(s, ch, possession(ch)); assert rc
    assert record_delivery(s, rc)
    return role_use(s)


# --- M2 temporal / lineage -------------------------------------------------
# A1: explicit revocation of the CURRENT approval after a renewal was appended
#     but before the switch commits. Contract: revocation BLOCKS the lane.
s = released_state(); a1 = append_approval(s, 'APPROVAL_RENEW_SAME_CONFIG', s['now'] + 7200); m = material(s, a1, 'rv')
s['revokedApprovals'].add(digest(s['current']['approval']))
ack = switch_until_arm(s, m)
probe('A1-revoke-prior-after-append-blocks-commit', 'revocation of A0 after A1 appended still blocks A1 activation', commit_activation(s, m, ack), False)

# A2: old approval A0 expires mid-switch after A1 (renewal) was appended: A1 alone authorises.
s = released_state(); a0_end = s['current']['approval']['body']['expiresAt']; s['now'] = a0_end - 10
a1 = append_approval(s, 'APPROVAL_RENEW_SAME_CONFIG', s['now'] + 7200); m = material(s, a1, 'mid')
ack = switch_until_arm(s, m); s['now'] = a0_end + 1
ok = commit_activation(s, m, ack)
probe('A2-A0-expiry-mid-switch-A1-authorises', 'after pause, A0 time expiry does not block the appended A1 switch', ok, True)
probe('A2b-A0-expiry-mid-switch-then-delivery', 'postcommit delivery completes under A1', bool(ok) and cp_eligible(s, s['current'], deliver(s)), True)

# A3: ARM ack lost/slow (>60s) -> commit denied; Node is ARMED with g1 so a repeated ARM is refused.
s = released_state(); a1 = append_approval(s, 'APPROVAL_RENEW_SAME_CONFIG', s['now'] + 7200); m = material(s, a1, 'slow')
ack = switch_until_arm(s, m); s['now'] += 61
denied = commit_activation(s, m, ack)
rearm = node_command(s, m, command(s, m, 'ARM_EXACT_RELEASE'))
probe('A3-slow-ack-commit-denied', 'stale ARM ack never commits', denied, False)
probe('A3b-rearm-same-gate-while-armed-refused', 'duplicate ARM over ARMED gate refused (no silent re-key)', rearm, None)

# A4: gate restoration. After a completed switch to g1, a FRESH operator-signed
#     INVALIDATE g1 + ARM of the OLD release g0 (approval A0 still in window).
#     Contract: 'no old gate restoration'; old tokens must not survive the switch.
s = released_state(); old_m = {k: deepcopy(s['current'][k]) for k in ('approval', 'release', 'delegation', 'receipt')}
old_use = role_use(s)
a1 = append_approval(s, 'APPROVAL_RENEW_SAME_CONFIG', s['now'] + 7200); m1 = material(s, a1, 'g1'); s['switchPending'] = True; finish(s, m1)
cur = {k: s['current'][k] for k in ('approval', 'release', 'delegation')}
inv = node_command(s, cur, command(s, cur, 'INVALIDATE_EXACT_GATE')); record_ack(s, inv)
restore = node_command(s, old_m, command(s, old_m, 'ARM_EXACT_RELEASE'))
probe('A4-node-refuses-rearm-of-previously-invalidated-old-release', 'Node keeps invalidated gate/release terminal (monotonic)', restore is None, True)
probe('A4b-old-chain-token-after-restoration', 'old A0/g0 use token never accepted again by Node', node_accepts(s, {**old_m, 'ack': restore}, old_use) if restore else False, False)
probe('A4c-CP-still-refuses-old-chain', 'CP eligibility keeps refusing old chain (current pointer is g1)', cp_eligible(s, {**old_m, 'ack': restore}, old_use) if restore else False, False)

# A5: restart (new generation, gate NONE) then ARM of an OLD-generation release.
s = released_state(); old_m = {k: deepcopy(s['current'][k]) for k in ('approval', 'release', 'delegation')}
s['node']['generation'] = 'generation-1'; s['node']['gate'] = None
arm_old_gen = node_command(s, old_m, command(s, old_m, 'ARM_EXACT_RELEASE'))
probe('A5-ARM-refuses-release-of-other-generation', 'ARM requires release.generation == current Node generation', arm_old_gen is None, True)

# A6: two renewals forked from the same A0; after A1 is current, A1' cannot activate.
s = released_state(); a1 = append_approval(s, 'APPROVAL_RENEW_SAME_CONFIG', s['now'] + 7200); a1b = append_approval(s, 'APPROVAL_RENEW_SAME_CONFIG', s['now'] + 7100)
m1 = material(s, a1, 'f1'); s['switchPending'] = True; finish(s, m1)
m2 = material(s, a1b, 'f2'); s['switchPending'] = True
cur = {k: s['current'][k] for k in ('approval', 'release', 'delegation')}
ia = node_command(s, cur, command(s, cur, 'INVALIDATE_EXACT_GATE')); record_ack(s, ia)
ack = node_command(s, m2, command(s, m2, 'ARM_EXACT_RELEASE')); record_ack(s, ack)
probe('A6-forked-sibling-approval-cannot-activate', 'priorApprovalHash/expected pointer CAS rejects sibling', commit_activation(s, m2, ack), False)

# A7: READMIT/REFRESH after only-time-expiry WITHOUT REAPPROVE are denied.
s = released_state(); s['now'] += 700
probe('A7-refresh-after-expiry-denied', 'REFRESH denied after approval expiry', refresh_same_generation(s, candidate(s)), False)
s2 = deepcopy(s); s2['node']['generation'] = 'generation-1'; s2['node']['gate'] = None
probe('A7b-readmit-after-expiry-denied', 'READMIT denied after approval expiry', readmit_allowed(s2, candidate(s2)), False)

# A8: renewal appended while mutation fence becomes active before commit.
s = released_state(); a1 = append_approval(s, 'APPROVAL_RENEW_SAME_CONFIG', s['now'] + 7200); m = material(s, a1, 'fence')
ack = switch_until_arm(s, m); s['cohortFence'] = True
probe('A8-fence-after-append-blocks-commit', 'active cohort mutation fence blocks activation', commit_activation(s, m, ack), False)

# A9: unrelated workers offline is not read: state flag is inert.
s = released_state(); s['otherWorkers'] = 'ALL_FOUR_OFFLINE_EXPIRED'
a1 = append_approval(s, 'APPROVAL_RENEW_SAME_CONFIG', s['now'] + 7200)
probe('A9-unrelated-offline-not-a-dependency', 'per-Node renewal proceeds with other workers offline', a1 is not None, True)

# --- M3 delivery / scope ---------------------------------------------------
# B1: PoP over a challenge copied for ANOTHER Node's ledger (cross-node replay).
s = released_state(); a1 = append_approval(s, 'APPROVAL_RENEW_SAME_CONFIG', s['now'] + 7200); m = material(s, a1, 'xn')
ack = switch_until_arm(s, m); assert commit_activation(s, m, ack); ch = delivery_challenge(s)
other = deepcopy(s); other['static'] = {**other['static'], 'nodeId': 'node-other'}
probe('B1-cross-node-challenge-replay', 'challenge bound to Node identity', consume_possession(other, ch, possession(ch)) is None, True)
# B2: receipt recorded, then CP lease expired: business denied; REFRESH restores without new delivery.
use = deliver(s); s['now'] += 301
probe('B2-lease-expired-business-denied', 'expired 300s lease denies CP eligibility', cp_eligible(s, s['current'], role_use(s)), False)
probe('B2b-refresh-same-generation-after-lease-expiry', 'REFRESH same generation renews lease', refresh_same_generation(s, candidate(s)), True)
# B3: ObservationScope with businessAuthority flipped or extra paths is schema-rejected.
av = F.observation_scope(s)
probe('B3-scope-businessAuthority-true-rejected', 'AVAILABLE scope cannot carry businessAuthority', shape('observationScope', {**av, 'businessAuthority': True}), False)
probe('B3b-scope-business-path-rejected', 'scope paths limited to observation literals', shape('observationScope', {**av, 'paths': ['/v1/executions']}), False)
# B4: safety raw-path aliases.
saf = {'nodeId': 'n', 'epoch': 'e', 'action': 'CANCEL_EXACT_COMMAND', 'method': 'POST', 'path': '/v1/executions/cancel', 'permitHash': 'a' * 64, 'bodyHash': 'a' * 64, 'nonce': 'a' * 64, 'issuedAt': 1, 'expiresAt': 2}
for alias in ('/v1/executions/cancel/', '/v1/executions/%63ancel', '//v1/executions/cancel', '/V1/executions/cancel'):
    probe('B4-safety-alias-' + alias, 'no alias of literal path', shape('safety', {**saf, 'path': alias}), False)
# B5: clock boundary and type confusion.
cap = json.loads((OWNER / 'stateful-positive.json').read_bytes())['clockCapability']
budget = json.loads((OWNER / 'stateful-positive.json').read_bytes())['budget']
edge = deepcopy(cap); edge['hostClock']['clockOffsetMillis'] = 29900; edge['hostClock']['uncertaintyMillis'] = 100
probe('B5-clock-boundary-equal-30000-allowed', 'abs(offset)+uncertainty <= 30000 inclusive', F.clocks_valid(edge, budget), True)
for label, value in (('bool', True), ('huge', 10 ** 20)):
    bad = deepcopy(cap); bad['guestClock']['clockOffsetMillis'] = value
    probe('B5-clock-offset-' + label + '-rejected', 'strict signed integer within range', F.clocks_valid(bad, budget), False)
# B6: authority matrix semantic invariant (not only equality): runtime/use issuer
#     never EXECUTE an approval/release/delivery-final procedure in the PROPOSED matrix.
pol = authority_build(); online = {'sv_b_runtime', 'sv_b_use_issuer', 'sv_b_verifier'}
protected = ('b_append_approval', 'b_commit_node_activation', 'b_record_key_delivery', 'b_prepare_key_delivery', 'b_consume_key_challenge', 'b_member_cas', 'b_begin_node_switch')
probe('B6-no-online-principal-on-protected-procedures', 'online principals have no protected EXECUTE', any(set(pol['procedures'][p]['execute']) & online for p in protected), False)
# B7: inv.nodes.status shared by online verifier observation and containment writers.
w = pol['tables']['inv.nodes']; shared = sorted({c for x in w for c in x['columns'] if sum(c in y['columns'] for y in w) > 1})
probe('B7-containment-column-not-writable-by-online-observer', 'online VER observation cannot write containment status', shared == [], True)
pub = pol['procedures']['b_public_node_observation']
probe('B7b-runtime-public-nodes-status-transition-defined', 'runtime-writable public.nodes.status has a stated one-way transition rule', 'transitions' in pub, True)
# B8: delivery/receipt signer custody: controller artifacts signed by OPERATOR_RELEASE anchor.
sp = pol['signaturePurposes']
probe('B8-delivery-controller-has-distinct-signer-or-stated-purpose-restriction', 'controller signer distinct from approval/release anchor or caller-purpose restriction stated', sp['KEY_DELIVERY_RECEIPT']['signer'] != sp['RELEASE']['signer'] or 'delivery' in json.dumps(pol['principals']['sv_b_operator']).lower(), True)

res = {'level': 'SYMBOLIC_REVIEWER_PROBES', 'probes': len(PROBES), 'agree': sum(p['agreesWithContract'] for p in PROBES), 'disagree': [p['id'] for p in PROBES if not p['agreesWithContract']], 'results': PROBES}
(HERE / 'adversarial-result.json').write_bytes((json.dumps(res, indent=2, default=str) + '\n').encode())
print(json.dumps({k: res[k] for k in ('probes', 'agree', 'disagree')}))
