"""Closed proposed Rev5 shapes, extending immutable Rev4; no actual protocols."""
from copy import deepcopy
import json
from pathlib import Path

E = Path(__file__).resolve().parent
H = {'type': 'string', 'pattern': '^[0-9a-f]{64}$(?![\\s\\S])'}
I = {'type': 'string', 'minLength': 1, 'maxLength': 128, 'pattern': '^[A-Za-z0-9][A-Za-z0-9_.:-]*$(?![\\s\\S])'}
T = {'type': 'integer', 'minimum': 1, 'maximum': 9007199254740991}
U = {'type': 'integer', 'minimum': 0, 'maximum': 9007199254740991}


def obj(properties):
    return {'type': 'object', 'additionalProperties': False, 'required': list(properties), 'properties': properties}


def ref(name):
    return {'$ref': '#/$defs/' + name}


def build():
    prior = json.loads((E.parent / 'fleet5-b-contract-rev4-20261106-codex/contract.schema.json').read_bytes())
    d = prior['$defs']
    for name in ('approval',):
        d[name]['properties']['rootLineageID'] = H
        d[name]['required'].append('rootLineageID')
    d['lineageTombstone'] = obj({'rootLineageID': H, 'revokedAncestorHash': H,
                               'nodeId': I, 'epoch': I, 'causalEvidenceHash': H,
                               'version': T, 'issuedAt': T})
    d['gateControl']['properties'].update({'expectedPriorRecordHash': H, 'expectedPriorSequence': U})
    d['gateControl']['required'] += ['expectedPriorRecordHash', 'expectedPriorSequence']
    d['gateAck']['properties'].update({'sequence': T, 'priorSequence': U})
    d['gateAck']['required'] += ['sequence', 'priorSequence']
    d['durableGateRecord'] = obj({'commandHash': H, 'priorRecord': H, 'generation': I,
                                  'sequence': T, 'state': {'enum': ['ARMED', 'INVALIDATED']},
                                  'gateId': I, 'releaseHash': H, 'delegationHash': H,
                                  'staticHash': H})
    d['gateObserveInput'] = obj({'nonce': H})
    available = obj({'status': {'const': 'AVAILABLE'}, 'businessAuthority': {'const': False},
                     'method': {'const': 'POST'}, 'path': {'const': '/v1/roles/observe'},
                     'nodeId': I, 'epoch': I, 'generation': I, 'nonce': H,
                     'observedAt': T, 'expiresAt': T, 'recordId': H,
                     'record': ref('durableGateRecord'), 'sequence': T,
                     'retiredGateIDs': {'type': 'array', 'uniqueItems': True, 'items': I},
                     'retiredReleaseHashes': {'type': 'array', 'uniqueItems': True, 'items': H},
                     'originalAckHash': H, 'originalAckExpiresAt': T})
    refused = obj({'status': {'enum': ['SCOPE_DENIED', 'UNKNOWN_RECORD', 'STALE_ACK', 'CONFLICT', 'EXPIRED']},
                   'businessAuthority': {'const': False}, 'nodeId': I, 'nonce': H,
                   'observedAt': T, 'reason': {'enum': ['AUTHENTICATION', 'MISSING_DURABLE_PROOF',
                   'ORIGINAL_ACK_EXPIRED', 'INCONSISTENT_HISTORY', 'READBACK_EXPIRED']},
                   'recovery': {'const': 'B-RECOVERY1_HOLD'}})
    d['gateObservation'] = {'oneOf': [available, refused]}
    d['signerRequest'] = obj({'authenticatedCaller': I, 'kind': I, 'purpose': I,
                              'domain': I, 'scopeHash': H, 'bodyHash': H})
    d['signedEnvelope']['properties']['kind']['enum'] += ['GATE_OBSERVATION', 'LINEAGE_TOMBSTONE']
    prior['$id'] = 'urn:saintvision:proposal:fleet5-b-rev5'
    prior['description'] = 'PROPOSED SCHEMA/STATIC/SYMBOLIC only; strict decoder and authenticated current state semantics required. No implemented protocol or actual keys.'
    return deepcopy(prior)


if __name__ == '__main__':
    (E / 'contract.schema.json').write_bytes((json.dumps(build(), indent=2) + '\n').encode())
