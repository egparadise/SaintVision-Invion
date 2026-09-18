"""Current registry authority, bound to the signed workload through frozen bytes."""
import json
from .errors import DomainError
from .model_manifest import canonical, rejected
from .model_registry_binding import ModelRegistryBindingStore
from .workspace_files import decode_snapshot

REGISTRY_FILE = "model/registry.json"


def current_registry(conn, database, principal, binding, registry_version_id):
    policy = getattr(database, "registry_binding_policy", None)
    if policy is None and registry_version_id is None:
        # Explicitly unconfigured legacy kernel-only execution, not registry approval.
        return None
    if policy is None or registry_version_id is None:
        raise DomainError("MODEL-0008", "Configured policy and exact registry binding required", 403)
    return ModelRegistryBindingStore(database, policy).revalidate(
        conn, principal, binding["project_id"], registry_version_id,
        binding["model_id"], binding["model_version"], manifest_hash=binding["manifest_sha256"])


def frozen_registry(conn, database, principal, binding, raw, workspace_id):
    _, files = decode_snapshot(raw, workspace_id)
    encoded = files.get(REGISTRY_FILE)
    if encoded is None:
        return current_registry(conn, database, principal, binding, None)
    try:
        saved = json.loads(encoded)
        registry_id = saved["registryVersionId"]
        if not isinstance(registry_id, str):
            rejected()
    except (ValueError, TypeError, KeyError):
        rejected()
    current = current_registry(conn, database, principal, binding, registry_id)
    if current is None or encoded != canonical(current):
        rejected()
    return current
