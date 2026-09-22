# RLS / authentication boundary evidence

- collected_at: 2026-09-22T14:51:40+00:00 · git HEAD: `b988ca7a` · collector: `tools/collect_rls_evidence.py`
- provenance: collector sha256 `d540c8e906e460bf590674921e7555342c4cd9e5303315560cab78054898def2` · baseline sha256 `920d01ca5f20fbb5f23c5c2434ac9d1e3063a452ccb5a8754ae4980ea42730ef` · uncommitted sources: ['tools/collect_rls_evidence.py']
- database: `inv_rls_7bd9a4f0a8314b5c835bb826ceb65d71` · PostgreSQL 16.15 · migration head `0046_model_manifest_readiness` · observer role `invowner` (superuser=True, bypassrls=True)
- GUC `inv.tenant_id`: unset value `None` · tenant A `796add6e-1595-4346-8c4f-aca28bace610` · known tenants 2
- verdict: **1 violation(s)** (E1..E6; an unverifiable row identity makes the verdict UNMEASURED, never PASS)
- rerun: `INV_AUDIT_DSN=<owner dsn> python tools/collect_rls_evidence.py --out-dir <dir>` (DSN value is never recorded)
- condition: Codex 50-placement load lane on the same PostgreSQL server ended (22:38 KST) before this run; this collector has no timing assertions

## Accepted exceptions (tools/rls-boundary-baseline.json)

| rule | role | table | reason |
|---|---|---|---|
| E2 | inv_app | public.tenants | Tenant registry: the row is the tenant, so no tenant_id scope applies. 0001_s02_baseline grants SELECT to inv_app on purpose. Cross-tenant enumeration of slug/display_name remains a design observation for Codex. |
| E3 | inv_app | public.tenants | Tenant registry: the row is the tenant, so no tenant_id scope applies. 0001_s02_baseline grants SELECT to inv_app on purpose. Cross-tenant enumeration of slug/display_name remains a design observation for Codex. |
| E4 | inv_app | public.tenants | Tenant registry: the row is the tenant, so no tenant_id scope applies. 0001_s02_baseline grants SELECT to inv_app on purpose. Cross-tenant enumeration of slug/display_name remains a design observation for Codex. |
| E5 | inv_app | public.tenants | Tenant registry: the row is the tenant, so no tenant_id scope applies. 0001_s02_baseline grants SELECT to inv_app on purpose. Cross-tenant enumeration of slug/display_name remains a design observation for Codex. |
| E2 | inv_discovery_issuer | public.tenants | 0045_discovery_machine_credentials grants SELECT(tenant_id) only, to validate tenant existence while issuing machine credentials. |
| E3 | inv_discovery_issuer | public.tenants | 0045_discovery_machine_credentials grants SELECT(tenant_id) only, to validate tenant existence while issuing machine credentials. |
| E4 | inv_discovery_issuer | public.tenants | 0045_discovery_machine_credentials grants SELECT(tenant_id) only, to validate tenant existence while issuing machine credentials. |
| E5 | inv_discovery_issuer | public.tenants | 0045_discovery_machine_credentials grants SELECT(tenant_id) only, to validate tenant existence while issuing machine credentials. |
| E2 | inv_discovery_issuer_guard | public.discovery_credential_issue_budgets | 0045 budget guard role reads issue budgets across tenants to enforce the issuer budget trigger; it is NOLOGIN and used only by the budget trigger function. |

## Violations

| rule | role | object | detail |
|---|---|---|---|
| E2 | inv_app | public.audit_events | tenant-scoped readable table without enabled+forced RLS |

## role `inv_app`

superuser=False bypassrls=False login=False member_of=[]

| table | scoped | RLS | privileges | policies | truth total / A / other | unset | A | A-foreign | A-identity | unknown | not-uuid |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `inv.account_provisioning_events` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.approval_audit` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.approval_dispatches` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.approval_nonces` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.approval_requests` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.approval_review_snapshots` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.approval_votes` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.business_admin_grants` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.business_projects` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.business_runs` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.business_subjects` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.checkpoint_objects` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.checkpoints` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.consumer_inbox` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.containment_approvals` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.containment_challenges` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.containment_requests` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.containment_votes` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.credential_grants` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.credential_versions` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.evidence` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.execution_attempts` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.execution_deliveries` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.git_operations` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.git_votes` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.idempotency` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.model_manifests` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.model_registry_bindings` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.model_retry_lineage` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.model_run_inputs` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.model_runtime_inputs` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.model_shard_locations` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.node_channel_audit` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.node_channels` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.node_controls` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.node_probes` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.node_resource_snapshots` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.node_stop_receipts` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.nodes` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.operator_grants` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.outbox` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.output_ingestions` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.project_grants` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.project_nodes` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.project_resource_limits` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.projects` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.reservation_aborts` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.resource_leases` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.resources` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.result_commitments` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.result_completions` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.run_attempts` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.runs` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.shard_commands` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.shard_completions` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.shard_parents` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.shard_plans` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.shard_recoveries` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.shard_recovery_members` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.shard_recovery_requests` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.storage_budgets` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.storage_objects` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.storage_parts` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.storage_sample_consumptions` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.storage_sample_requests` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.tenant_controls` | yes | on+forced | - | tenant_isolation[ALL] | 2 / 1 / 1 | - | - | - | - | - | - |
| `inv.tenants` | yes | on+forced | - | tenant_isolation[ALL] | 2 / 1 / 1 | - | - | - | - | - | - |
| `inv.terminal_connections` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.terminal_frame_audit` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.terminal_frame_intents` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.terminal_tickets` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.tool_claims` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.workspace_checkouts` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.workspace_edits` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.workspace_restores` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.workspace_resumptions` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.workspace_starts` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `public.acceptance_records` | yes | on+forced | S,I,U,D | acceptance_records_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.approvals` | yes | on+forced | S,I,U,D | approvals_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.artifacts` | yes | on+forced | S,I,U,D | artifacts_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.audit_events` | yes | off | S,I | - | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | 0 |
| `public.backup_records` | yes | on+forced | S,I,U,D | backup_records_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.checkpoints` | yes | on+forced | S,I,U,D | checkpoints_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.code_commits` | yes | on+forced | S,I,U,D | code_commits_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.container_images` | yes | on+forced | S,I,U,D | container_images_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.context_bundle_items` | yes | on+forced | S,I,U,D | context_bundle_items_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.context_bundles` | yes | on+forced | S,I,U,D | context_bundles_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.context_snapshots` | yes | on+forced | S,I | context_snapshots_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.data_locations` | yes | on+forced | S,I,U,D | data_locations_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.data_replicas` | yes | on+forced | S,I,U,D | data_replicas_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.dataset_versions` | yes | on+forced | S,I,U(col) | dataset_versions_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.datasets` | yes | on+forced | S,I,U,D | datasets_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.deployments` | yes | on+forced | S,I,U,D | deployments_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.discovery_credential_events` | yes | on+forced | S,I | discovery_credential_events_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.discovery_machine_credentials` | yes | on+forced | S,U(col) | discovery_machine_credentials_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.distributed_plans` | yes | on+forced | S,I,U,D | distributed_plans_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.eval_cases` | yes | on+forced | S,I,U,D | eval_cases_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.eval_results` | yes | on+forced | S,I,U,D | eval_results_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.eval_runs` | yes | on+forced | S,I,U,D | eval_runs_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.eval_suites` | yes | on+forced | S,I,U,D | eval_suites_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.evidence_envelopes` | yes | on+forced | S,I | evidence_envelopes_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.execution_bindings` | yes | on+forced | S | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.idempotency_records` | yes | on+forced | S,I,U,D | idempotency_records_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.inbox_events` | yes | on+forced | S,I,U,D | inbox_events_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.model_lineage` | yes | on+forced | S,I,U,D | model_lineage_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.model_versions` | yes | on+forced | S,I,U(col) | model_versions_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.models` | yes | on+forced | S,I,U,D | models_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.node_announcements` | yes | on+forced | S,I,U,D | node_announcements_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.node_bootstrap_tokens` | yes | on+forced | S,I,U,D | node_bootstrap_tokens_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.node_capabilities` | yes | on+forced | S,I,U,D | node_capabilities_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.node_links` | yes | on+forced | S,I,U,D | node_links_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.nodes` | yes | on+forced | S,I,U,D | nodes_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.outbox_events` | yes | on+forced | S,I,U,D | outbox_events_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.permission_snapshots` | yes | on+forced | S,I,U,D | permission_snapshots_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.plan_placements` | yes | on+forced | S,I,U,D | plan_placements_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.project_members` | yes | on+forced | S,I,U,D | project_members_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.projects` | yes | on+forced | S,I,U,D | projects_tenant_isolation[ALL] | 2 / 1 / 1 | 0 | 1 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.recovery_drills` | yes | on+forced | S,I,U,D | recovery_drills_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.release_manifests` | yes | on+forced | S,I,U,D | release_manifests_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.resource_offers` | yes | on+forced | S,I,U,D | resource_offers_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.resource_pool_members` | yes | on+forced | S,I,U,D | resource_pool_members_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.resource_pools` | yes | on+forced | S,I,U,D | resource_pools_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.resource_snapshots` | yes | on+forced | S,I,U,D | resource_snapshots_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.roles` | yes | on+forced | S,I,U,D | roles_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.run_attempts` | yes | on+forced | S,I,U,D | run_attempts_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.run_record_artifacts` | yes | on+forced | S,I | run_record_artifacts_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.run_records` | yes | on+forced | S,I | run_records_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.runs` | yes | on+forced | S,I,U,D | runs_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.steps` | yes | on+forced | S,I,U,D | steps_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.storage_checks` | yes | on+forced | S,I,U,D | storage_checks_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.storage_contributions` | yes | on+forced | S,I,U,D | storage_contributions_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.tenants` | yes | off | S | - | 2 / 1 / 1 | 2 | 2 | 1 | DIFFERENT (ctid) | 2 | 2 |
| `public.upload_sessions` | yes | on+forced | S,I,U,D | upload_sessions_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.user_roles` | yes | on+forced | S,I,U,D | user_roles_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.users` | yes | on+forced | S,I,U,D | users_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.workloads` | yes | on+forced | S,I,U,D | workloads_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.workspace_edit_locks` | yes | on+forced | S | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.workspace_volumes` | yes | on+forced | S,I,U,D | workspace_volumes_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.workspaces` | yes | on+forced | S,I,U,D | workspaces_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |

| SECURITY DEFINER function | execute |
|---|---|
| `public.apply_capability_offer(uuid, character, character, bigint)` | yes |
| `public.apply_resource_offer(uuid, character, text, bigint)` | no |
| `public.business_admin_allowed(uuid, text, text)` | yes |
| `public.business_execution_permission(uuid, text, character)` | yes |
| `public.consume_discovery_issue_budget(uuid)` | no |
| `public.model_location_readiness(text[])` | no |
| `public.model_registry_snapshot(uuid, text, text)` | no |
| `public.node_by_certificate(character)` | yes |
| `public.project_kernel_link(uuid, text)` | yes |
| `public.run_committed_outputs(uuid, text)` | no |
| `public.subject_kernel_link(uuid, character)` | yes |
| `public.workspace_input_state(uuid, text)` | yes |

## role `inv_kernel`

superuser=False bypassrls=False login=False member_of=[]

| table | scoped | RLS | privileges | policies | truth total / A / other | unset | A | A-foreign | A-identity | unknown | not-uuid |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `inv.account_provisioning_events` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.approval_audit` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.approval_dispatches` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.approval_nonces` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.approval_requests` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.approval_review_snapshots` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.approval_votes` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.business_admin_grants` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.business_projects` | yes | on+forced | S,U(col) | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.business_runs` | yes | on+forced | S | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.business_subjects` | yes | on+forced | S,U(col) | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.checkpoint_objects` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.checkpoints` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.consumer_inbox` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.containment_approvals` | yes | on+forced | S,I,U(col) | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.containment_challenges` | yes | on+forced | S,I,U(col) | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.containment_requests` | yes | on+forced | S,I,U(col) | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.containment_votes` | yes | on+forced | S,I,U(col) | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.control_epoch` | no | off | S,U(col) | - | 0 / - / - | 0 | 0 | - | - | 0 | 0 |
| `inv.credential_grants` | yes | on+forced | S | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.credential_versions` | yes | on+forced | S | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.evidence` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.execution_attempts` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.execution_deliveries` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.git_operations` | yes | on+forced | S,I,U(col) | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.git_votes` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.idempotency` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.model_manifests` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.model_registry_bindings` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.model_retry_lineage` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.model_run_inputs` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.model_runtime_inputs` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.model_shard_locations` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.node_channel_audit` | yes | on+forced | S | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.node_channels` | yes | on+forced | S,U(col) | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.node_controls` | yes | on+forced | S,I(col),U(col) | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.node_probes` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.node_resource_snapshots` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.node_stop_receipts` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.nodes` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.operator_grants` | yes | on+forced | S,U(col) | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.outbox` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.output_ingestions` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.project_grants` | yes | on+forced | S,U(col) | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.project_nodes` | yes | on+forced | S,U(col) | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.project_resource_limits` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.projects` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.reservation_aborts` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.resource_leases` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.resources` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.result_commitments` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.result_completions` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.run_attempts` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.runs` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.shard_commands` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.shard_completions` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.shard_parents` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.shard_plans` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.shard_recoveries` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.shard_recovery_members` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.shard_recovery_requests` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.storage_budgets` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.storage_objects` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.storage_parts` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.storage_sample_consumptions` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.storage_sample_requests` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.tenant_controls` | yes | on+forced | S,I(col),U(col) | tenant_isolation[ALL] | 2 / 1 / 1 | 0 | 1 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.tenants` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 2 / 1 / 1 | 0 | 1 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.terminal_connections` | yes | on+forced | S,I,U(col) | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.terminal_frame_audit` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.terminal_frame_intents` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.terminal_tickets` | yes | on+forced | S,I,U(col) | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.tool_claims` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.workspace_checkouts` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.workspace_edits` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.workspace_restores` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.workspace_resumptions` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.workspace_starts` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.data_locations` | yes | on+forced | S(col),U(col) | storage_kernel_tenant[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (pk) | 0 | denied 22P02 |
| `public.execution_bindings` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.nodes` | yes | on+forced | S(col),U(col) | storage_kernel_tenant[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (pk) | 0 | denied 22P02 |
| `public.project_members` | yes | on+forced | S(col),U(col) | kernel_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (pk) | 0 | denied 22P02 |
| `public.projects` | yes | on+forced | S(col),U(col) | kernel_tenant_isolation[ALL] | 2 / 1 / 1 | 0 | 1 | 0 | same (pk) | 0 | denied 22P02 |
| `public.runs` | yes | on+forced | S(col),U(col) | kernel_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (pk) | 0 | denied 22P02 |
| `public.storage_checks` | yes | on+forced | S,I | storage_kernel_tenant[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.storage_contributions` | yes | on+forced | S(col),U(col) | storage_kernel_tenant[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (pk) | 0 | denied 22P02 |
| `public.users` | yes | on+forced | S(col),U(col) | kernel_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (pk) | 0 | denied 22P02 |
| `public.workloads` | yes | on+forced | S(col),U(col) | kernel_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (pk) | 0 | denied 22P02 |
| `public.workspace_edit_locks` | yes | on+forced | S,I,U(col) | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.workspaces` | yes | on+forced | S(col),U(col) | kernel_tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (pk) | 0 | denied 22P02 |

| SECURITY DEFINER function | execute |
|---|---|
| `public.apply_capability_offer(uuid, character, character, bigint)` | no |
| `public.apply_resource_offer(uuid, character, text, bigint)` | no |
| `public.business_admin_allowed(uuid, text, text)` | no |
| `public.business_execution_permission(uuid, text, character)` | no |
| `public.consume_discovery_issue_budget(uuid)` | no |
| `public.model_location_readiness(text[])` | yes |
| `public.model_registry_snapshot(uuid, text, text)` | yes |
| `public.node_by_certificate(character)` | no |
| `public.project_kernel_link(uuid, text)` | no |
| `public.run_committed_outputs(uuid, text)` | no |
| `public.subject_kernel_link(uuid, character)` | no |
| `public.workspace_input_state(uuid, text)` | no |

## role `inv_runtime_dev`

superuser=False bypassrls=False login=True member_of=['inv_kernel']

| table | scoped | RLS | privileges | policies | truth total / A / other | unset | A | A-foreign | A-identity | unknown | not-uuid |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `inv.account_provisioning_events` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.approval_audit` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.approval_dispatches` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.approval_nonces` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.approval_requests` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.approval_review_snapshots` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.approval_votes` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.business_admin_grants` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.business_projects` | yes | on+forced | S,U(col) | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.business_runs` | yes | on+forced | S | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.business_subjects` | yes | on+forced | S,U(col) | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.checkpoint_objects` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.checkpoints` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.consumer_inbox` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.containment_approvals` | yes | on+forced | S,I,U(col) | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.containment_challenges` | yes | on+forced | S,I,U(col) | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.containment_requests` | yes | on+forced | S,I,U(col) | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.containment_votes` | yes | on+forced | S,I,U(col) | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.control_epoch` | no | off | S,U(col) | - | 0 / - / - | 0 | 0 | - | - | 0 | 0 |
| `inv.credential_grants` | yes | on+forced | S | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.credential_versions` | yes | on+forced | S | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.evidence` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.execution_attempts` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.execution_deliveries` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.git_operations` | yes | on+forced | S,I,U(col) | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.git_votes` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.idempotency` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.model_manifests` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.model_registry_bindings` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.model_retry_lineage` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.model_run_inputs` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.model_runtime_inputs` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.model_shard_locations` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.node_channel_audit` | yes | on+forced | S | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.node_channels` | yes | on+forced | S,U(col) | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.node_controls` | yes | on+forced | S,I(col),U(col) | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.node_probes` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.node_resource_snapshots` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.node_stop_receipts` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.nodes` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.operator_grants` | yes | on+forced | S,U(col) | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.outbox` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.output_ingestions` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.project_grants` | yes | on+forced | S,U(col) | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.project_nodes` | yes | on+forced | S,U(col) | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.project_resource_limits` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.projects` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.reservation_aborts` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.resource_leases` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.resources` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.result_commitments` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.result_completions` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.run_attempts` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.runs` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.shard_commands` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.shard_completions` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.shard_parents` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.shard_plans` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.shard_recoveries` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.shard_recovery_members` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.shard_recovery_requests` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.storage_budgets` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.storage_objects` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.storage_parts` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.storage_sample_consumptions` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.storage_sample_requests` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.tenant_controls` | yes | on+forced | S,I(col),U(col) | tenant_isolation[ALL] | 2 / 1 / 1 | 0 | 1 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.tenants` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 2 / 1 / 1 | 0 | 1 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.terminal_connections` | yes | on+forced | S,I,U(col) | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.terminal_frame_audit` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.terminal_frame_intents` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.terminal_tickets` | yes | on+forced | S,I,U(col) | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.tool_claims` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.workspace_checkouts` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.workspace_edits` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.workspace_restores` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.workspace_resumptions` | yes | on+forced | S,I,U,D | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `inv.workspace_starts` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.data_locations` | yes | on+forced | S(col),U(col) | - | 0 / 0 / 0 | 0 | 0 | 0 | same (pk) | 0 | denied 22P02 |
| `public.execution_bindings` | yes | on+forced | S,I | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.nodes` | yes | on+forced | S(col),U(col) | - | 0 / 0 / 0 | 0 | 0 | 0 | same (pk) | 0 | denied 22P02 |
| `public.project_members` | yes | on+forced | S(col),U(col) | - | 0 / 0 / 0 | 0 | 0 | 0 | same (pk) | 0 | denied 22P02 |
| `public.projects` | yes | on+forced | S(col),U(col) | - | 2 / 1 / 1 | 0 | 1 | 0 | same (pk) | 0 | denied 22P02 |
| `public.runs` | yes | on+forced | S(col),U(col) | - | 0 / 0 / 0 | 0 | 0 | 0 | same (pk) | 0 | denied 22P02 |
| `public.storage_checks` | yes | on+forced | S,I | - | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.storage_contributions` | yes | on+forced | S(col),U(col) | - | 0 / 0 / 0 | 0 | 0 | 0 | same (pk) | 0 | denied 22P02 |
| `public.users` | yes | on+forced | S(col),U(col) | - | 0 / 0 / 0 | 0 | 0 | 0 | same (pk) | 0 | denied 22P02 |
| `public.workloads` | yes | on+forced | S(col),U(col) | - | 0 / 0 / 0 | 0 | 0 | 0 | same (pk) | 0 | denied 22P02 |
| `public.workspace_edit_locks` | yes | on+forced | S,I,U(col) | tenant_isolation[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (ctid) | 0 | denied 22P02 |
| `public.workspaces` | yes | on+forced | S(col),U(col) | - | 0 / 0 / 0 | 0 | 0 | 0 | same (pk) | 0 | denied 22P02 |

| SECURITY DEFINER function | execute |
|---|---|
| `public.apply_capability_offer(uuid, character, character, bigint)` | no |
| `public.apply_resource_offer(uuid, character, text, bigint)` | no |
| `public.business_admin_allowed(uuid, text, text)` | no |
| `public.business_execution_permission(uuid, text, character)` | no |
| `public.consume_discovery_issue_budget(uuid)` | no |
| `public.model_location_readiness(text[])` | yes |
| `public.model_registry_snapshot(uuid, text, text)` | yes |
| `public.node_by_certificate(character)` | no |
| `public.project_kernel_link(uuid, text)` | no |
| `public.run_committed_outputs(uuid, text)` | no |
| `public.subject_kernel_link(uuid, character)` | no |
| `public.workspace_input_state(uuid, text)` | no |

## role `inv_discovery_issuer`

superuser=False bypassrls=False login=False member_of=[]

| table | scoped | RLS | privileges | policies | truth total / A / other | unset | A | A-foreign | A-identity | unknown | not-uuid |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `inv.account_provisioning_events` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.approval_audit` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.approval_dispatches` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.approval_nonces` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.approval_requests` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.approval_review_snapshots` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.approval_votes` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.business_admin_grants` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.business_projects` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.business_runs` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.business_subjects` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.checkpoint_objects` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.checkpoints` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.consumer_inbox` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.containment_approvals` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.containment_challenges` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.containment_requests` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.containment_votes` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.credential_grants` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.credential_versions` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.evidence` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.execution_attempts` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.execution_deliveries` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.git_operations` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.git_votes` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.idempotency` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.model_manifests` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.model_registry_bindings` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.model_retry_lineage` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.model_run_inputs` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.model_runtime_inputs` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.model_shard_locations` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.node_channel_audit` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.node_channels` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.node_controls` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.node_probes` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.node_resource_snapshots` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.node_stop_receipts` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.nodes` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.operator_grants` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.outbox` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.output_ingestions` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.project_grants` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.project_nodes` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.project_resource_limits` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.projects` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.reservation_aborts` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.resource_leases` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.resources` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.result_commitments` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.result_completions` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.run_attempts` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.runs` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.shard_commands` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.shard_completions` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.shard_parents` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.shard_plans` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.shard_recoveries` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.shard_recovery_members` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.shard_recovery_requests` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.storage_budgets` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.storage_objects` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.storage_parts` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.storage_sample_consumptions` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.storage_sample_requests` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.tenant_controls` | yes | on+forced | - | tenant_isolation[ALL] | 2 / 1 / 1 | - | - | - | - | - | - |
| `inv.tenants` | yes | on+forced | - | tenant_isolation[ALL] | 2 / 1 / 1 | - | - | - | - | - | - |
| `inv.terminal_connections` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.terminal_frame_audit` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.terminal_frame_intents` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.terminal_tickets` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.tool_claims` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.workspace_checkouts` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.workspace_edits` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.workspace_restores` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.workspace_resumptions` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.workspace_starts` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `public.discovery_credential_events` | yes | on+forced | I | discovery_credential_events_issuer_access[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `public.discovery_machine_credentials` | yes | on+forced | S(col),I(col),U(col) | discovery_machine_credentials_issuer_access[ALL] | 0 / 0 / 0 | 0 | 0 | 0 | same (pk) | 0 | 0 |
| `public.execution_bindings` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `public.tenants` | yes | off | S(col) | - | 2 / 1 / 1 | 2 | 2 | 1 | DIFFERENT (pk) | 2 | 2 |
| `public.workspace_edit_locks` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |

| SECURITY DEFINER function | execute |
|---|---|
| `public.apply_capability_offer(uuid, character, character, bigint)` | no |
| `public.apply_resource_offer(uuid, character, text, bigint)` | no |
| `public.business_admin_allowed(uuid, text, text)` | no |
| `public.business_execution_permission(uuid, text, character)` | no |
| `public.consume_discovery_issue_budget(uuid)` | yes |
| `public.model_location_readiness(text[])` | no |
| `public.model_registry_snapshot(uuid, text, text)` | no |
| `public.node_by_certificate(character)` | no |
| `public.project_kernel_link(uuid, text)` | no |
| `public.run_committed_outputs(uuid, text)` | no |
| `public.subject_kernel_link(uuid, character)` | no |
| `public.workspace_input_state(uuid, text)` | no |

## role `inv_discovery_issuer_guard`

superuser=False bypassrls=False login=False member_of=[]

| table | scoped | RLS | privileges | policies | truth total / A / other | unset | A | A-foreign | A-identity | unknown | not-uuid |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `inv.account_provisioning_events` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.approval_audit` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.approval_dispatches` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.approval_nonces` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.approval_requests` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.approval_review_snapshots` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.approval_votes` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.business_admin_grants` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.business_projects` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.business_runs` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.business_subjects` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.checkpoint_objects` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.checkpoints` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.consumer_inbox` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.containment_approvals` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.containment_challenges` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.containment_requests` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.containment_votes` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.credential_grants` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.credential_versions` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.evidence` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.execution_attempts` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.execution_deliveries` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.git_operations` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.git_votes` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.idempotency` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.model_manifests` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.model_registry_bindings` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.model_retry_lineage` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.model_run_inputs` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.model_runtime_inputs` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.model_shard_locations` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.node_channel_audit` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.node_channels` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.node_controls` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.node_probes` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.node_resource_snapshots` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.node_stop_receipts` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.nodes` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.operator_grants` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.outbox` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.output_ingestions` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.project_grants` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.project_nodes` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.project_resource_limits` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.projects` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.reservation_aborts` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.resource_leases` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.resources` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.result_commitments` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.result_completions` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.run_attempts` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.runs` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.shard_commands` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.shard_completions` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.shard_parents` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.shard_plans` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.shard_recoveries` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.shard_recovery_members` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.shard_recovery_requests` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.storage_budgets` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.storage_objects` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.storage_parts` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.storage_sample_consumptions` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.storage_sample_requests` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.tenant_controls` | yes | on+forced | - | tenant_isolation[ALL] | 2 / 1 / 1 | - | - | - | - | - | - |
| `inv.tenants` | yes | on+forced | - | tenant_isolation[ALL] | 2 / 1 / 1 | - | - | - | - | - | - |
| `inv.terminal_connections` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.terminal_frame_audit` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.terminal_frame_intents` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.terminal_tickets` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.tool_claims` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.workspace_checkouts` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.workspace_edits` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.workspace_restores` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.workspace_resumptions` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `inv.workspace_starts` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `public.discovery_credential_issue_budgets` | yes | off | S(col),I,U(col) | - | 0 / 0 / 0 | 0 | 0 | 0 | same (pk) | 0 | 0 |
| `public.execution_bindings` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |
| `public.workspace_edit_locks` | yes | on+forced | - | tenant_isolation[ALL] | 0 / 0 / 0 | - | - | - | - | - | - |

| SECURITY DEFINER function | execute |
|---|---|
| `public.apply_capability_offer(uuid, character, character, bigint)` | no |
| `public.apply_resource_offer(uuid, character, text, bigint)` | no |
| `public.business_admin_allowed(uuid, text, text)` | no |
| `public.business_execution_permission(uuid, text, character)` | no |
| `public.consume_discovery_issue_budget(uuid)` | yes |
| `public.model_location_readiness(text[])` | no |
| `public.model_registry_snapshot(uuid, text, text)` | no |
| `public.node_by_certificate(character)` | no |
| `public.project_kernel_link(uuid, text)` | no |
| `public.run_committed_outputs(uuid, text)` | no |
| `public.subject_kernel_link(uuid, character)` | no |
| `public.workspace_input_state(uuid, text)` | no |

## SECURITY DEFINER catalogue

| function | owner | config | execute grants |
|---|---|---|---|
| `public.apply_capability_offer(uuid, character, character, bigint)` | invowner | search_path=pg_catalog | inv_app |
| `public.apply_resource_offer(uuid, character, text, bigint)` | invowner | search_path=pg_catalog | - |
| `public.business_admin_allowed(uuid, text, text)` | invowner | search_path=pg_catalog | inv_app |
| `public.business_execution_permission(uuid, text, character)` | invowner | search_path=pg_catalog | inv_app |
| `public.consume_discovery_issue_budget(uuid)` | inv_discovery_issuer_guard | search_path=pg_catalog, public | inv_discovery_issuer |
| `public.model_location_readiness(text[])` | invowner | search_path=pg_catalog | inv_kernel |
| `public.model_registry_snapshot(uuid, text, text)` | invowner | search_path=pg_catalog | inv_kernel |
| `public.node_by_certificate(character)` | invowner | search_path=pg_catalog, public | inv_app |
| `public.project_kernel_link(uuid, text)` | invowner | search_path=pg_catalog | inv_app |
| `public.run_committed_outputs(uuid, text)` | invowner | search_path=pg_catalog | - |
| `public.subject_kernel_link(uuid, character)` | invowner | search_path=pg_catalog | inv_app |
| `public.workspace_input_state(uuid, text)` | invowner | search_path=pg_catalog | inv_app |
