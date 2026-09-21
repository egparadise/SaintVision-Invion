---
doc_id: "DISCOVERY-MACHINE-CREDENTIAL-ADR-001"
title: "Discovery machine credential least-privilege contract"
version: "1.1.3"
status: "accepted"
author: "Codex"
reviewer: "pending"
mapped_at_sha: "462304bbf4f7d0fdce7c3ee4ee10cd9d8224698e"
updated: "2026-09-21T22:33:42+09:00"
source_of_truth: "Git"
tags: ["discovery", "credential", "tenant", "bootstrap", "security"]
---

# ADR-097: tenant-bound discovery credential

**Status:** Accepted for the interim operator-CLI path. The CLI and the PostgreSQL-tested rolling issuance quota are in integration at `6dcd09dd69729e7651aae62b54bb6fd2d3858636`. Real Node binary/physical-node onboarding and protected delivery-channel acceptance remain unverified.
**Date:** 2026-09-21 KST
**Decision:** The user approved an operator CLI as the temporary credential issuer. Operators bind a credential to one tenant and installation, then inject it through an approved protected delivery path. Issuance authority remains with designated operators. A future protected tenant-operator API is an open long-term decision; this acceptance does not choose it.
**Deciders:** User (operational path decision); Codex (security/contract implementation); designated Identity/operations owners (operator account and delivery-channel operation)
**Base:** branch `agent/codex/terminal-pty-contract`, operator CLI anchor `462304bbf4f7d0fdce7c3ee4ee10cd9d8224698e`; current integration `6dcd09dd69729e7651aae62b54bb6fd2d3858636`

## Decision

Adopt a per-installation, tenant-bound, short-lived `discovery:announce` grant issued by `tools/discovery_credential.py`. The operator CLI is the interim issuer; a protected API remains a later decision. The first-contact endpoint is not anonymous. The credential may only create or refresh its one linked unverified candidate, and normal OIDC authorization remains required for candidate review/admission and all other APIs.

Issuance requires a named PostgreSQL login explicitly granted membership in the `inv_discovery_issuer` database role. The role itself is `NOLOGIN`, `NOSUPERUSER`, `NOCREATEDB`, `NOCREATEROLE`, `NOINHERIT`, and `NOBYPASSRLS`; it can read tenant identifiers and perform only the credential/event operations needed by the CLI. Database administration grants membership to individually designated operators. Local access to the CLI or workstation alone is not issuer authorization. This issuer role is currently cross-tenant, so membership must remain restricted to named operators approved to provision any tenant; tenant-specific issuer delegation is not implemented.

The CLI reads `INV_DISCOVERY_ISSUER_DSN` from the process environment. It supports a read-only preflight and requires `--apply` to write. It rejects issuance unless stdout is an interactive terminal. After the transaction commits it displays the bearer exactly once alongside a non-secret credential ID and expiry; the raw token is never written to the repository, database, argv, audit event, diagnostic, or application log. Operators must not run the command in a recorded/shared terminal and must transfer the visible value immediately through the organization-approved protected channel. The repository does not name or verify that channel; if an approved channel is unavailable, onboarding remains blocked.

The bearer has 256 bits of randomness, is stored only as SHA-256 digest, expires after 15 minutes, and is rate-limited to one announcement per 30 seconds. Re-issue atomically revokes the previous active grant for that tenant/installation. Operators can revoke by tenant and credential ID; admission and decline revoke outstanding linked credentials. Expired rows remain as audit/history records and fail authorization. The server returns the same 403 for unknown, mismatched, expired, and revoked grants while storing only safe reason codes in audit metadata.

This grants no proof of physical identity. A thief can falsify self-reported fields and refresh only the one bound candidate until expiry/revocation. They cannot create another candidate, act for another tenant/install, list/admit candidates, mint enrollment credentials, enroll a node, access project data, or call ordinary user APIs. Operators must independently verify the claimed machine before admission.

## Context

The discovery announcement was intentionally anonymous so an unregistered Node could announce before it had an identity. The handler only wrote an unverified candidate, but the caller chose `X-Inv-Tenant`; an unauthenticated caller could insert candidates into another tenant and consume that tenant's 500-candidate limit. The earlier security fix bound the endpoint to an authenticated principal's tenant, which closed that cross-tenant write but also blocked first contact by a machine without a pre-provisioned OIDC token. This decision adds a separate machine-credential branch limited to first-contact announcements.

The one-time **enrollment** bootstrap token is issued only after a candidate exists and is approved, so it cannot authenticate the first discovery request. At proposal time, the repository lacked a discovery issuer. This branch now implements the scoped CLI and credential persistence; there is still no IdP service identity, organization-specific protected delivery channel, or long-term protected issuer API.

## Goals and non-goals

- Let an operator-authorized, not-yet-enrolled machine create one candidate in exactly one tenant without reopening anonymous cross-tenant writes.
- Keep announcement data explicitly self-reported and unverified; discovery must not enroll, admit, execute, or grant access.
- A leaked discovery credential must not act as a user credential or work on any other API.
- Implement the accepted interim operator-CLI path and state the remaining real-node/delivery boundaries without claiming production onboarding acceptance.

This credential is not node mTLS identity, the later one-time enrollment token, a user OIDC token, or proof that the machine's claimed hostname/capabilities are true.

## Options

| Option | Benefit | Cost / risk | Assessment |
|---|---|---|---|
| A. Put an existing user's OIDC access token in each Node service environment | Little protocol work; uses current `get_principal` | The machine holds a human credential with broader API authority and user lifecycle; no per-Node scope/revocation; a user token can outlive the discovery task. No approved operational issue/delivery procedure was found. | Do not adopt as the supported bootstrap path. A tenant-matched user token may be used only for a deliberate, short-lived operator diagnostic, not unattended enrollment. |
| B. Keep the announcement endpoint anonymous and rely on LAN reachability/rate limits | Preserves the original first-contact flow | LAN presence is not tenant identity; an internal caller can still spoof a tenant and exhaust its candidate limit. | Reject. It restores the exact boundary the current fix closed. |
| C. Issue a dedicated tenant- and installation-bound, short-lived opaque credential | Restores first contact with narrow, attributable authority and bounded leak impact | Requires an issuance/revocation store, issuer authorization, agent support, and secret delivery procedure. | **Recommend.** One credential may refresh exactly one linked candidate for a short window; operator admission/revocation ends it early. |

## Recommended credential contract

### Tenant and installation binding

- Issuance binds immutable `tenant_id` and the agent's stable `instance_id` (installation ID). Do not infer either from the request's tenant header or caller-supplied body.
- The server obtains tenant scope from the credential record. Keep `X-Inv-Tenant` only as a consistency assertion; reject mismatch before database scope/write. Require the exact bound `instance_id`.
- Enforce at most one announcement row for a credential, even if source IP changes. The current `(tenant, instance_id, source_ip)` upsert key alone is insufficient for this invariant; persist a credential-to-announcement link/unique key and update the observed IP on that same linked row.
- The source IP remains server-observed. Hostname, OS, CPU, RAM, GPU, labels, and installation ID remain claims unless independently attested; the response/UI must retain `verified: false`.

### Scope and leak impact

- Scope is exactly `discovery:announce` for the bound tenant and installation, on `POST /v1/discovery/announcements` only.
- The announcement route has a dedicated discovery-only verifier branch; it does not pass this credential through `get_principal`. Ordinary protected routes continue to use their own user/node authentication. If carried in `Authorization: Bearer`, shared proxy/access logs must redact that header.
- It cannot list candidates, admit/decline them, mint enrollment tokens, enroll Nodes, read tenant/project data, create workloads, request PTY tickets, or call other user APIs. Other endpoints continue to require their own OIDC principal or enrolled-node mTLS contract; the discovery secret must not be accepted as a `Principal`.
- A stolen credential can create or refresh the one linked candidate and lie in that candidate's self-reported fields until expiry/revocation. It cannot create multiple candidates or refresh arbitrary installations. The human admission step must verify the expected installation out of band; a candidate is not proof of machine identity. This residual spoof/substitution risk must be visible to the admitting operator.
- The server enforces one announcement per credential per 30 seconds. Because an issuer can choose many installation IDs, unlimited credential issuance could still fill a tenant's 500-candidate allowance, even though each bearer is tenant/install-bound. The DB trigger now allows at most 10 issuer-role credential inserts per tenant in any rolling 24 hours, atomically across concurrent CLI/direct-SQL writers. This limits operator mistakes and burst compromise; it does not stop a persistent authorized issuer from reaching the 500-candidate ceiling over multiple days. Keep issuer membership narrow and monitor the audit/candidate queues. Never log the raw secret or put it in argv, URL, error, evidence, or database plaintext.
- **Quota boundary:** the trigger charges only inserts executed with `current_user = inv_discovery_issuer`, which covers the named issuer login and `SET ROLE inv_discovery_issuer` direct-SQL path. A PostgreSQL superuser or the owner of `discovery_machine_credentials` can issue an INSERT outside that role identity and bypass the quota. This is intentional: those cluster/database administration identities are outside the ordinary issuer threat model. Restrict and audit them separately; the 10/24h control is not a cap on privileged database administration. This boundary is also stated beside the migration trigger so future reviewers do not mistake the role-scoped check for a universal database limit.
- PostgreSQL quota evidence includes sequential 10+1 CLI and direct-SQL denial plus a 12-worker barrier-start race test: exactly 10 issuance transactions succeed, two are refused, and the committed credential, issued-event, and rolling-budget timestamp counts are each exactly 10. This directly verifies the tenant budget-row serialization and that rejected trigger exceptions roll back their timestamp append. The concurrent integration case passed on an owned disposable PostgreSQL 16 container; it is not a hosted-CI run.

### Secret format, expiry, and use

- Generate at least 256 bits of cryptographic randomness and return an opaque, versioned token once. Store only a keyed digest or a cryptographic hash of the random secret plus non-secret credential metadata; compare in constant time.
- Recommended interim grant: exact tenant + installation binding, 15-minute expiry, reusable only for that linked candidate, with rate-limited 30-second refreshes. This matches `inv-discover`'s normal cadence and the current 300-second candidate freshness rule, giving the operator a bounded review window. Revoke the grant on admission or explicit operator action. If it expires before review, issue a replacement only after checking the existing candidate; do not silently broaden scope.
- A single-request token is narrower but the candidate goes stale after the 300-second freshness window unless the operator reviews immediately or explicitly includes stale candidates. A long-lived/no-expiry repeating token is rejected because a leak could keep a false candidate live indefinitely.

### Issuance, rotation, revocation, and audit

- Issuer must be explicitly authorized and separate from a normal project member. The accepted interim authority is membership in the dedicated `inv_discovery_issuer` PostgreSQL role, granted by a database administrator to named operator logins. A future tenant-level operator grant/API remains open. Do not equate a valid OIDC user or local CLI access with issuance authority.
- On issuance, record credential ID, tenant, installation ID, exact scope, issuer, issue/expiry time, and state. The CLI shows the secret once in interactive stdout after commit; operators then use an approved protected channel. No secret is stored for later retrieval.
- Re-issue by atomically revoking any unused credential for the same tenant/installation and creating a new credential. Revoke by credential ID; consumption, expiry, and revocation are terminal. Successful admission/enrollment should revoke any outstanding grants for that installation.
- Audit issue, revoke, each accepted refresh, expiry, rejection, issuer, tenant, credential ID, installation ID, timestamps, and outcome. Never include raw token bytes. Rejections must not reveal whether another tenant's credential exists.

## Minimum interim onboarding path

The interim path is implemented in this branch except for an actual Node binary/physical-node exercise and an organization-specific protected handoff channel:

1. Operator verifies the tenant and assigns/generates the stable installation ID for the physical machine.
2. A database administrator provisions a named operator login and grants it membership in `inv_discovery_issuer`. The operator receives its DSN through the approved secret manager/environment injection as `INV_DISCOVERY_ISSUER_DSN`; do not put DSN contents in shell history, a script, source, or report. Run the CLI preflight, then issue with `--apply` in a private, non-recorded interactive terminal:
   `python tools/discovery_credential.py issue --tenant <tenant-uuid> --installation <stable-installation-id> --apply`
   The command shows the bearer once after commit. Keep the non-secret `credentialId` and `expiresAt` for lifecycle actions; never copy the bearer into a log or ticket.
3. Deliver the bearer only through the organization's approved protected channel and inject it into the Node service environment as `INV_DISCOVERY_BEARER_TOKEN`. Do not put the secret in a command argument, source, ordinary ticket, terminal transcript, screenshot, or log.
4. Run the agent's normal 30-second announcement loop with the short-lived credential. It can create/update only one explicitly unverified candidate until expiry or revocation. Stop the loop when the candidate is under review or enrollment completes.
5. An authenticated tenant operator checks the candidate's installation ID and observed source details against the physical machine out of band, then uses the existing candidate admission path. The returned one-time **enrollment** token is delivered to that machine and exchanged at `POST /v1/nodes`; the machine then uses its enrolled node credential/mTLS. These are separate grants and must not be conflated.
6. Admission/decline revokes the linked grant. For an incident or planned retirement, an authorized operator can revoke it explicitly:
   `python tools/discovery_credential.py revoke --tenant <tenant-uuid> --credential-id <dcr-credential-id> --apply`
   Expired grants are rejected without cleanup jobs; their metadata remains for audit, and a re-issue rotates/revokes an older grant. Confirm no bearer appears in service logs. If an approved issuer login or protected delivery channel is unavailable, the node remains blocked; do not fall back to anonymous announcement or a long-lived human token.

The temporary route is operator CLI issuance and protected out-of-band delivery of a per-installation, short-lived scoped credential. The long-term protected issuer API remains an open decision. The actual approved delivery channel is still an operational prerequisite not identifiable from this repository.

## Decision record and remaining long-term choices

1. **Tenant binding (decided):** bind tenant in the machine grant and require `X-Inv-Tenant` to match it.
2. **Scope (decided):** allow only `discovery:announce` for one installation; do not reuse a user's general OIDC bearer.
3. **Expiry/use (decided):** 15-minute grant, one linked candidate, 30-second minimum interval; no long-lived renewal.
4. **Rotation (decided):** operator re-issue atomically revokes the previous grant for that tenant/installation.
5. **Revocation (decided):** durable `revoked_at`; explicit operator revoke and admission/decline revoke linked credentials.
6. **Audit and issuance budget (decided):** append-only metadata events for issue, revoke, accepted refresh, admission and denial; raw bearer is excluded. The database enforces 10 issuer-role issues per tenant per rolling 24 hours, including inserts that bypass the CLI. This is burst control, not a complete defense against sustained abuse; raising the limit requires a reviewed operational decision.
7. **Issuer:** accepted interim choice is operator CLI using explicit membership in the dedicated `inv_discovery_issuer` DB role. A protected tenant-operator API remains open as the long-term option. A normal project-member role or workstation access alone is insufficient.
8. **Delivery:** existing approved secret manager/service injection if Identity/operations confirms one, otherwise a narrowly controlled out-of-band handoff. The repository currently proves neither channel exists.
9. **Temporary anonymous endpoint:** not recommended and not included. The existing tenant-spoofing/candidate-cap attack would return.

## Acceptance evidence and remaining boundary

- Cross-tenant mismatch, wrong installation ID, expired, revoked, random, and wrong-scope credentials fail before candidate write; a matching grant can refresh only the same linked candidate and cannot create another row, including after source IP changes.
- Mutation controls prove removing each tenant/scope/use/expiry check makes its corresponding test fail.
- A matching bearer can refresh only its linked candidate. An HTTP attempt to list candidates with that same discovery bearer is 403; exhaustive probing of every other API route was not part of this run.
- Issuer authorization, token secrecy, API first announcement, candidate admission, automatic and explicit revocation, expiry, and safe audit metadata are exercised against a disposable PostgreSQL and the FastAPI HTTP boundary. Unit guard-removal controls also prove tenant, expiry, and revocation checks.
- Issuance-budget integration exhausts 10 tenant issues, verifies the 11th CLI request is refused without revealing a secret, then attempts a direct issuer-role SQL insert and confirms the database trigger refuses it with no extra credential/audit/budget row. This closes the CLI-bypass path. A persistent authorized issuer can still add up to 10 per tenant per 24 hours and eventually hit the candidate ceiling.
- Not yet evidenced: actual `inv-discover` binary execution, physical Node service secret injection through the organization's approved protected channel, one-time enrollment exchange on a real Node, and enrolled-node mTLS. Therefore the protocol/CLI implementation is ready for controlled operator testing, but real-node onboarding is not yet declared operationally restored.

## Current implementation evidence and limitations

Implementation in this branch adds migration `0045_discovery_machine_cred`, the `inv_discovery_issuer` role, issuer CLI, digest-only credential/event tables, a DB-enforced per-tenant rolling issue budget, scoped announcement verification, rotation, explicit revocation, and admission/decline revocation. Disposable PostgreSQL HTTP integration exercises CLI dry-run/issue/revoke, successful first announcement and refresh, admission revocation, explicit revocation, cross-tenant/install/expiry denial, budget exhaustion, direct-SQL denial, and no-candidate-on-denial. The Python guard suite was mutation-tested by removing tenant, expiry, and revocation checks separately; each corresponding test failed, then the source was restored. Go compilation/runtime and physical Node onboarding were not run because Go is unavailable on this development host. No production credential was issued.
