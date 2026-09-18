"""Strict public operator policy configuration; never accepted from a workload."""
from .model_registry_binding import RegistryBindingPolicy


def configured_registry_policy(value):
    if not isinstance(value, dict) or set(value) != {"version", "allowed"}:
        raise ValueError("Explicit registry policy object required")
    entries = value["allowed"]
    if not isinstance(entries, list) or not 1 <= len(entries) <= 64:
        raise ValueError("Bounded registry policy allowlist required")
    pairs = []
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"licensePolicy", "classification"}:
            raise ValueError("Exact license/classification pair required")
        pair = (entry["licensePolicy"], entry["classification"])
        if any(not isinstance(part, str) or not 1 <= len(part) <= 256 for part in pair):
            raise ValueError("Bounded license/classification strings required")
        if pair in pairs:
            raise ValueError("Duplicate registry policy pair")
        pairs.append(pair)
    return RegistryBindingPolicy(value["version"], frozenset(pairs))
