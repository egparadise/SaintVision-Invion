---
doc_id: "DISCOVERY-MACHINE-CREDENTIAL-ADR-001"
title: "Discovery machine credential least-privilege contract proposal"
version: "1.0.0"
status: "proposed"
author: "Codex"
reviewer: "pending"
mapped_at_sha: "a1d72856feb6a8421ddea1601edc27ee9c9f57c5"
updated: "2026-09-21T20:03:00+09:00"
source_of_truth: "Git"
tags: ["discovery", "credential", "tenant", "bootstrap", "security"]
---

# ADR-097 proposal: tenant-bound discovery credential

**Status:** Proposed; user decision pending. This is a contract/design proposal, not an implemented or operational credential workflow.
**Date:** 2026-09-21 KST
**Deciders:** User; Codex (security/contract design); Identity and operations owners (issuer and delivery procedure)
**Base:** integration `a1d72856feb6a8421ddea1601edc27ee9c9f57c5`

## Context

The discovery announcement was intentionally anonymous so an unregistered Node could announce before it had an identity. The handler only wrote an unverified candidate, but the caller chose `X-Inv-Tenant`; an unauthenticated caller could insert candidates into another tenant and consume that tenant's 500-candidate limit. The current security fix binds announcements to an authenticated principal's tenant. It also means a new machine without a pre-provisioned OIDC user access token cannot make its first announcement.

The repository has a one-time **enrollment** bootstrap token, but it is issued only after a candidate exists and is approved. It cannot authenticate the first discovery request. There is no repository implementation for issuing a discovery machine credential, registering an IdP service identity, or delivering/rotating such a secret. The Node runbook's secret-manager instruction describes a destination only, not an issuer or operational procedure.

## Goals and non-goals

- Let an operator-authorized, not-yet-enrolled machine create one candidate in exactly one tenant without reopening anonymous cross-tenant writes.
- Keep announcement data explicitly self-reported and unverified; discovery must not enroll, admit, execute, or grant access.
- A leaked discovery credential must not act as a user credential or work on any other API.
- Define an implementable interim path. Do not claim the current branch already supports it.

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
- The announcement route needs a dedicated discovery-credential verifier/dependency; do not pass this credential through `get_principal` or accept it on ordinary user routes. If carried in `Authorization: Bearer`, ensure shared proxy/access logs redact that header.
- It cannot list candidates, admit/decline them, mint enrollment tokens, enroll Nodes, read tenant/project data, create workloads, request PTY tickets, or call other user APIs. Other endpoints continue to require their own OIDC principal or enrolled-node mTLS contract; the discovery secret must not be accepted as a `Principal`.
- A stolen credential can create or refresh the one linked candidate and lie in that candidate's self-reported fields until expiry/revocation. It cannot create multiple candidates or refresh arbitrary installations. The human admission step must verify the expected installation out of band; a candidate is not proof of machine identity. This residual spoof/substitution risk must be visible to the admitting operator.
- Rate-limit issuance per tenant/issuer and announcement attempts per source/token. Never log the raw secret or put it in argv, URL, error, evidence, or database plaintext.

### Secret format, expiry, and use

- Generate at least 256 bits of cryptographic randomness and return an opaque, versioned token once. Store only a keyed digest or a cryptographic hash of the random secret plus non-secret credential metadata; compare in constant time.
- Recommended interim grant: exact tenant + installation binding, 15-minute expiry, reusable only for that linked candidate, with rate-limited 30-second refreshes. This matches `inv-discover`'s normal cadence and the current 300-second candidate freshness rule, giving the operator a bounded review window. Revoke the grant on admission or explicit operator action. If it expires before review, issue a replacement only after checking the existing candidate; do not silently broaden scope.
- A single-request token is narrower but the candidate goes stale after the 300-second freshness window unless the operator reviews immediately or explicitly includes stale candidates. A long-lived/no-expiry repeating token is rejected because a leak could keep a false candidate live indefinitely.

### Issuance, rotation, revocation, and audit

- Issuer must be an explicitly authorized tenant operator, separate from a normal project member. The precise permission source is open: a tenant-level operator grant/API, or an audited operator CLI backed by a dedicated provisioning identity. Do not equate any valid OIDC user with permission to issue machine credentials.
- On issuance, record credential ID, tenant, installation ID, exact scope, issuer, issue/expiry time, and state. Show the secret once through an approved protected channel. No issuance API/CLI exists today.
- Re-issue by atomically revoking any unused credential for the same tenant/installation and creating a new credential. Revoke by credential ID; consumption, expiry, and revocation are terminal. Successful admission/enrollment should revoke any outstanding grants for that installation.
- Audit issue, revoke, each accepted refresh, expiry, rejection, issuer, tenant, credential ID, installation ID, timestamps, and outcome. Never include raw token bytes. Rejections must not reveal whether another tenant's credential exists.

## Minimum interim onboarding path

This is the smallest path recommended to unblock the first Node without an anonymous endpoint; **none of these credential-issuer steps are implemented yet**:

1. Operator verifies the tenant and assigns/generates the stable installation ID for the physical machine.
2. An authorized issuer creates a tenant + installation bound, `discovery:announce` credential with 15-minute expiry. A future protected CLI is the shortest implementation option; a tenant-operator API is preferable once the operator permission model exists. Both must store only the digest and audit issuance. It can refresh one linked candidate at most once per 30 seconds.
3. Deliver the one-time secret directly through a protected operator channel and load it in the Node service environment as `INV_DISCOVERY_BEARER_TOKEN`. Do not paste it into a shell command, CLI option, source, ordinary ticket, or log.
4. Run the agent's normal 30-second announcement loop with the short-lived credential. It can create/update only one explicitly unverified candidate until expiry or revocation. Stop the loop when the candidate is under review or enrollment completes.
5. An authenticated tenant operator checks the candidate's installation ID and observed source details against the physical machine out of band, then uses the existing candidate admission path. The returned one-time **enrollment** token is delivered to that machine and exchanged at `POST /v1/nodes`; the machine then uses its enrolled node credential/mTLS. These are separate grants and must not be conflated.
6. Revoke the discovery credential at admission (or on denial); confirm no secret appears in logs. If step 2–3 cannot be performed with an approved issuer/channel, the node remains blocked; do not fall back to anonymous announcement or a long-lived human token.

The interim route is operator issuance and secure out-of-band delivery of a per-installation, short-lived scoped credential, not the current code's generic OIDC bearer environment variable. It becomes an executable procedure only after the issuer, persistence/validation, CLI or API, audit, Node client behavior, and protected delivery channel are implemented and tested. The real Identity/operations owner must confirm whether a suitable secure delivery channel already exists.

## Alternatives and decisions for the user

1. **Tenant binding:** trust `X-Inv-Tenant` (reject); require a current user OIDC principal and derive tenant from it (secure for interactive callers, but does not solve an unregistered machine); or bind tenant in the machine grant and require the header to match it (recommend for machine onboarding).
2. **Scope:** reuse a user's general OIDC bearer (reject for unattended Nodes); create a tenant-wide service identity (broader than needed); or grant only `discovery:announce` for one installation (recommend).
3. **Expiry/use:** single request then consume (narrowest, but candidate becomes stale after 300 seconds unless the operator acts promptly); short-lived 15-minute grant with 30-second refreshes for one linked candidate (recommend); long-lived/no-expiry renewal (reject).
4. **Rotation:** automatically refresh using the same credential (easy but extends exposure); or operator re-issues a replacement that atomically revokes the previous grant (recommend initially).
5. **Revocation:** stateless/self-contained credential with expiry-only revocation (simple, but leaked token remains usable); or durable credential state with `revoked_at` and admission-linked revoke (recommend for prompt response).
6. **Audit:** infrastructure logs only (may miss tenant-level actor context); or append-only business audit for issue, revoke, accepted refresh and denial with token ID but no secret (recommend; security logs may supplement).
7. **Issuer:** protected operator API (recommended long-term, but needs a tenant-operator authority) or operator CLI (shortest interim implementation, but requires a dedicated provisioning identity and auditable host controls). A normal project-member role is not sufficient by itself.
8. **Delivery:** existing approved secret manager/service injection if Identity/operations confirms one, otherwise a narrowly controlled out-of-band handoff. The repository currently proves neither channel exists.
9. **Temporary anonymous endpoint:** not recommended and not included. The existing tenant-spoofing/candidate-cap attack would return.

## Acceptance evidence required before calling onboarding restored

- Cross-tenant mismatch, wrong installation ID, expired, revoked, random, and wrong-scope credentials fail before candidate write; a matching grant can refresh only the same linked candidate and cannot create another row, including after source IP changes.
- Mutation controls prove removing each tenant/scope/use/expiry check makes its corresponding test fail.
- A stolen-grant simulation can create at most the one bound unverified candidate and cannot call list/admission/enrollment/other tenant endpoints.
- Issuer authorization, token secrecy in logs/CLI/audit, secure delivery, one-time enrollment exchange, revocation, and audit are exercised end-to-end in the chosen operator channel.
- New Node journey succeeds from no prior identity through discovery, human admission, bootstrap-token exchange, and enrolled-node authentication. Until all steps are evidenced, onboarding stays blocked/unverified.

## Current implementation evidence and limitations

At base `a1d72856feb6a8421ddea1601edc27ee9c9f57c5`, the API requires a principal and enforces tenant equality; `inv-discover` sends `INV_DISCOVERY_BEARER_TOKEN` as Authorization Bearer. Focused TestClient proves cross-tenant 403/no DB call and missing credential 401, with guard-removal rollback failure. This does not prove issuance, machine scope, real OIDC/IdP delivery, or successful first-time Node onboarding. Go build/test was not run because Go is absent on the development host. No new code or credential was created as part of this proposal.
