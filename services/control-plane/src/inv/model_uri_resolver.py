"""Operational ``inv://models`` resolver across the kernel/business role boundary."""

from copy import deepcopy

from sqlalchemy.orm import Session

from saintvision.db.session import tenant_scope
from saintvision.errors import InvError, RES_ARTIFACT_NOT_FOUND
from saintvision.services.resolver import resolve_model

from .approvals import ApprovalStore
from .business_auth import permission
from .contracts import validate_contract
from .errors import DomainError
from .model_view import ModelExecutionManifestObservation


class ModelUriResolver:
    """Bind the injected manifest reader to a fresh project-authorized kernel view.

    The business engine is deliberately the restricted ``inv_app`` engine.  It
    cannot read ``inv.model_manifests`` or ``inv.model_shard_locations``; the
    only value crossing that boundary is the strict, schema-checked observation.
    Every GET calls both authorization boundaries again, so a prior success is
    never a replay credential after membership or grant revocation.
    """

    def __init__(self, database, business_engine):
        self.db = database
        self.business_engine = business_engine
        self.manifests = ModelExecutionManifestObservation(database)

    @staticmethod
    def _checked(result: dict) -> dict:
        validate_contract("ModelExecutionManifestObservation", result)
        return result

    def _authorized_user(self, principal, project: str) -> str:
        with self.db.transaction(principal.tenant_id) as conn:
            ApprovalStore(self.db)._grant(conn, project, principal.subject_id, "can_request")
            return permission(conn, project, principal.subject_id, "can_request", linked=True)[
                "userId"
            ]

    def get(self, principal, project: str, uri: str) -> dict:
        user_id = self._authorized_user(principal, project)
        observation: dict | None = None

        def read_manifest(_tenant_id, model_id, version):
            nonlocal observation
            observation = self.manifests.get(principal, project, model_id, version)
            return observation

        try:
            with Session(self.business_engine) as session, session.begin():
                with tenant_scope(session, principal.tenant_id):
                    resolved = resolve_model(
                        session,
                        tenant_id=principal.tenant_id,
                        project_id=project,
                        uri=uri,
                        reader_user_id=user_id,
                        manifest_reader=read_manifest,
                    )
        except InvError as error:
            if error.code == RES_ARTIFACT_NOT_FOUND:
                raise DomainError("MODEL-0004", "Committed model not found", 404) from None
            raise DomainError("VAL-0002", "Model URI could not be resolved", 422) from None
        except ValueError:
            raise DomainError("VAL-0002", "Invalid immutable model URI", 422) from None

        if observation is None or resolved.locations is None:
            raise DomainError("MODEL-0001", "Model resolver observation is inconsistent", 409)
        checks = {
            (item.shard_index, item.location_id, item.location_version): item
            for item in resolved.locations
        }
        result = deepcopy(observation)
        for item in result["shardLocations"]:
            identity = (
                int(item["shardIndex"]),
                item["locationId"],
                int(item["locationVersion"]),
            )
            checked = checks.get(identity)
            if checked is None:
                raise DomainError("MODEL-0001", "Model resolver observation is inconsistent", 409)
            # Intersection only: the business recheck can remove a node observed
            # by the kernel, never introduce one the kernel did not report.
            item["readyNodes"] = checked.ready_nodes
            item["materialisable"] = checked.materialisable
        shard_indexes = {int(shard["index"]) for shard in result["shards"]}
        ready_shards = {
            int(item["shardIndex"]) for item in result["shardLocations"] if item["materialisable"]
        }
        result["materialisable"] = ready_shards == shard_indexes
        return self._checked(result)
