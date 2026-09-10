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
    settings = dict(settings)
    destinations = settings.pop("destinations", [])
    git_repositories = settings.pop("gitRepositories", [])
    if not isinstance(git_repositories, list) or len(git_repositories) > 16:
        raise ValueError("At most sixteen explicit Git repositories are allowed")
    if not isinstance(destinations, list) or len(destinations) > 4:
        raise ValueError("At most five trusted Workspace Nodes including the default are allowed")
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
    result = WorkspaceAPI(
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
    pool = {result.runtime.node.node_id: result.runtime}
    from .remote_git import GitHubRepository

    result.git_repositories = {}
    for repository in git_repositories:
        configured_git = GitHubRepository(**repository)
        if configured_git.alias in result.git_repositories:
            raise ValueError("Duplicate Git repository alias")
        result.git_repositories[configured_git.alias] = configured_git
    for target in destinations:
        if not isinstance(target, dict) or "destinations" in target or "gitRepositories" in target:
            raise ValueError("Flat trusted destination configuration required")
        if target.get("workingRoot") != settings["workingRoot"]:
            raise ValueError("Destinations must share the same authoritative editor root")
        configured = configured_workspace(database, tenant, target)
        if configured.runtime.node.node_id in pool:
            raise ValueError("Duplicate Workspace destination")
        pool[configured.runtime.node.node_id] = configured.runtime
    for runtime in pool.values():
        runtime.destinations = pool
    return result
