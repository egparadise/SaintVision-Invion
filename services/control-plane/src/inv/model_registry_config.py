"""Strict public operator policy configuration; never accepted from a workload."""
from saintvision.storage.readroot import ReadRoot
from .model_manifest import RootBinding
from .model_registry_binding import RegistryBindingPolicy


def configured_model_roots(value):
    """Build explicit full-byte verifier roots from trusted process configuration."""
    if not isinstance(value, dict) or set(value) != {"roots", "maxReadBytes"}:
        raise ValueError("Explicit model verifier configuration required")
    entries = value["roots"]
    maximum = value["maxReadBytes"]
    if (
        not isinstance(entries, list)
        or not 1 <= len(entries) <= 128
        or type(maximum) is not int
        or not 1 <= maximum <= 4 * 1099511627776
    ):
        raise ValueError("Bounded model verifier configuration required")
    roots = []
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {
            "nodeId",
            "contributionId",
            "contributionVersion",
            "path",
        }:
            raise ValueError("Exact model root binding required")
        if (
            not isinstance(entry["nodeId"], str)
            or not isinstance(entry["contributionId"], str)
            or type(entry["contributionVersion"]) is not int
            or entry["contributionVersion"] < 1
            or not isinstance(entry["path"], str)
        ):
            raise ValueError("Typed model root binding required")
        roots.append(
            RootBinding(
                entry["nodeId"],
                entry["contributionId"],
                entry["contributionVersion"],
                ReadRoot(entry["path"]),
            )
        )
    return {"roots": roots, "max_read_bytes": maximum}


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
