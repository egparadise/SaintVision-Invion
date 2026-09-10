"""Operator-only construction; no import paths or authority from HTTP input."""

from pathlib import Path
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from .node_transport import NodeTLSClient, private_key
from .sandbox import SandboxProfile
from .tooling import NodePrincipal
from .workspace_api import RestrictedWorkspaceRuntime, WorkspaceAPI
from .workspace_files import WorkingGenerations


def configured_workspace(database, tenant, settings):
    if set(settings) != {
        "workingRoot",
        "nodeId",
        "resources",
        "profile",
        "policyVersion",
        "signingKeyFile",
        "tls",
    }:
        raise ValueError("Explicit restricted Workspace configuration required")
    profile = dict(settings["profile"])
    profile["images"] = frozenset(profile["images"])
    profile["executables"] = frozenset(profile["executables"])
    signing_key = load_pem_private_key(
        Path(private_key(settings["signingKeyFile"])).read_bytes(),
        password=None,
    )
    if not isinstance(signing_key, Ed25519PrivateKey):
        raise ValueError("Ed25519 queue signing key required")
    return WorkspaceAPI(
        database,
        WorkingGenerations(settings["workingRoot"]),
        RestrictedWorkspaceRuntime(
            database,
            profile=SandboxProfile(**profile),
            node=NodePrincipal(tenant, settings["nodeId"]),
            resources=settings["resources"],
            signing_key=signing_key,
            policy_version=settings["policyVersion"],
            client=NodeTLSClient(**settings["tls"]),
        ),
    )
