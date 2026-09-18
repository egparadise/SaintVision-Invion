"""Explicit identity binding for trusted workers; no HTTP or execution authority.

Policy is operator configuration, never an assertion from a registry/UI caller.
The binding preserves historical identity; every reuse checks current permission,
registry lifecycle and policy. Existing runtime approval/fences remain mandatory.
"""
from dataclasses import dataclass
import hashlib
import re

from psycopg.types.json import Jsonb
from .approvals import ApprovalStore
from .business_auth import permission
from .errors import DomainError
from .model_manifest import canonical, manifest_copy, rejected


@dataclass(frozen=True)
class RegistryBindingPolicy:
    version: str
    allowed: frozenset[tuple[str, str]]

    def __post_init__(self):
        if (not isinstance(self.version, str) or not 1 <= len(self.version) <= 128
            or not isinstance(self.allowed, frozenset) or not 1 <= len(self.allowed) <= 64
            or any(not isinstance(p, tuple) or len(p) != 2
                   or any(not isinstance(s, str) or not 1 <= len(s) <= 256 for s in p)
                   for p in self.allowed)):
            raise ValueError('Explicit bounded registry binding policy required')

    @property
    def digest(self):
        return hashlib.sha256(canonical({'version': self.version, 'allowed': sorted(self.allowed)})).hexdigest()


class ModelRegistryBindingStore:
    def __init__(self, database, policy):
        if not isinstance(policy, RegistryBindingPolicy):
            raise ValueError('Operator registry binding policy required')
        self.db, self.policy = database, policy

    def bind(self, principal, project, registry_version_id, model_id, version, *, manifest_hash):
        # There is no model-name/version fallback or implicit registry lookup.
        if (not isinstance(registry_version_id, str) or len(registry_version_id) != 30
            or not isinstance(manifest_hash, str) or re.fullmatch('[0-9a-f]{64}', manifest_hash) is None):
            raise DomainError('MODEL-0008', 'Explicit registry and manifest identity required', 422)
        with self.db.transaction(principal.tenant_id) as conn:
            ApprovalStore(self.db)._grant(conn, project, principal.subject_id, 'can_request')
            permission(conn, project, principal.subject_id, 'can_request', linked=True)
            row = conn.execute(
                'SELECT manifest,manifest_sha256 FROM inv.model_manifests '
                'WHERE project_id=%s AND model_id=%s AND version=%s',
                (project, model_id, version),
            ).fetchone()
            if not row or row['manifest_sha256'] != manifest_hash:
                rejected()
            body = manifest_copy(row['manifest'])
            if (body['modelId'] != model_id or body['version'] != version
                or hashlib.sha256(canonical(body)).hexdigest() != manifest_hash
                or (body['licensePolicy'], body['classification']) not in self.policy.allowed):
                rejected()
            # Locks registry model + exact version through this transaction. The
            # definer grants no registry UPDATE or blanket SELECT to inv_kernel.
            registry = conn.execute('SELECT * FROM public.model_registry_snapshot(%s,%s,%s)',
                (principal.tenant_id, project, registry_version_id)).fetchone()
            now = conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
            if (not registry or registry['stage'] != 'released'
                or registry['content_hash'] != body['contentHash']
                or registry['byte_size'] != body['totalBytes']
                or registry['verified_at'] is None or registry['verified_at'] > now
                or registry['pinned_until'] is None or registry['pinned_until'] <= now):
                rejected()
            binding = {
                'tenantId': str(principal.tenant_id), 'projectId': project,
                'registryVersionId': registry_version_id,
                'registryModelId': registry['registry_model_id'],
                'registryVersion': registry['registry_version'],
                'modelId': model_id, 'version': version, 'manifestHash': manifest_hash,
                'contentHash': body['contentHash'], 'totalBytes': body['totalBytes'],
                'licensePolicy': body['licensePolicy'], 'classification': body['classification'],
                'bindingPolicyVersion': self.policy.version, 'bindingPolicyHash': self.policy.digest,
                'executionAuthorized': False, 'requiresExecutionRevalidation': True,
            }
            conn.execute('''INSERT INTO inv.model_registry_bindings
                (tenant_id,project_id,registry_version_id,model_id,model_version,manifest_sha256,binding)
                VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING''',
                (principal.tenant_id, project, registry_version_id, model_id, version,
                 manifest_hash, Jsonb(binding)))
            saved = conn.execute('SELECT binding FROM inv.model_registry_bindings '
                'WHERE project_id=%s AND registry_version_id=%s',
                (project, registry_version_id)).fetchone()
            if not saved or saved['binding'] != binding:
                raise DomainError('MODEL-0008', 'Registry identity already bound differently', 409)
            return binding
