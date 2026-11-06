# Pinned K1 clock interval mechanism and conditional convexity proof

Root adopted max1s UNCERTAINTY as a v1 policy budget, separately from K1's30s
proof skew. Actual authenticated clock source/measurement and running entrypoint
remain unprovisioned. Operational status is CLOCK_MECHANISM_HOLD until the full
source/stdlib obligations and actual source are independently reviewed/matched.
Failure is ERR[CLOCK_MECHANISM_UNPROVEN] or ERR[CLOCK_UNTRUSTED], never weaker
duplicated K1 checks or an optimistic past Now.

## Closed endpoint mechanism

Freeze ONE authenticated installed policy, packet, semantic/history/current
context, status/grant versions and challenge/attempt identity. Only Now varies.
The clock port supplies a continuous UTC uncertainty interval [L,U] and actual
UTC observation t0 with L<=t0<=U; all three are nonzero and the entire interval
excludes Go's zero instant. Invalid location/order/zero-crossing refuses
ERR[CLOCK_INTERVAL_INVALID]. Approved clock-source identity, uncertainty budget
and monotonic continuity are independently authenticated, not caller assertions.

1. Establish an authenticated UTC/monotonic mapping before acquisition. Propagate
   its bounds through measured elapsed acquisition time with the approved drift/
   uncertainty envelope; never freeze its initial UTC sample. Immediately before
   evaluation choose a bounded forward evaluation deadline, and [L,U] covering
   all possible realNow through both endpoint calls, t0 acquisition and returned
   evaluation. Propagated uncertainty plus the forward evaluation guard must fit
   the max1s envelope policy; if not, refuse. Acquisition itself need not finish
   in1s, but its elapsed time/drift and status ageing must be included. No timing
   guarantee is claimed and no widening to30s is allowed. Actual approved clock
   mapping/drift and evaluation guard bindings remain HOLD.
2. Build pinned K1 independently at L and U from those SAME immutable bytes and
   authenticated facts. Require Verify success at BOTH endpoints. If and only if
   this path has an authorized K1-current derivation contract, require
   VerifyCurrentProjectionSet success at BOTH endpoints too. Normal:3 leases
   that unchanged K1 cannot represent do not use this current path.
3. Require identical FULL Report (classification, counts, every digest) and, on
   that allowed current path, identical set digest/head/ordered member/operation/
   fence/authority/expiry bindings in the immutable snapshot. No security field
   is excluded. Pinned K1 Report has NO evaluated-at diagnostic. Only optional
   wrapper diagnostics such as wrapperEvaluatedAt/monotonic elapsed may differ;
   they never affect authorization or output comparison.
4. Obtain/retain actual approved t0 within the same bounded bracket and perform
   the returned K1 evaluation with Now=t0, not whichever endpoint passed. Require
   its same full security output and final monotonic deadline/clock continuity.
   Any expired bracket, version change, endpoint failure or output difference
   refuses ERR[CLOCK_INTERVAL_INVALID]/ERR[STALE_SNAPSHOT]. No silent retry.

The complete call is bounded; acquisition/evaluation that overruns the bracket
refuses rather than backdating t0. Later use, especially K2B admission, obtains
fresh clock/facts and separate permits; this endpoint result is not a lease.
Policy budget chosen does not mean an actual clock source was provisioned.

## Fixed-input proof domain

clock-predicate-inventory.json pins EVERY non-test Go file in eb32 migrationverify,
all direct Now selector sites, their time.Time type and transitive predicate
families. Any source/selector/type/branch change invalidates this proof pending
new review. There is no physical clock read in that K1 package. K1's x509 call
receives explicit nonzero CurrentTime on live paths; history supplies its original
nonzero signed/consuming time. Original native observedAt minimum1 excludes the
zero-time fallback. Policy rejects a UTC interval containing zero so NewVerifier's
IsZero test cannot create an interior hole. All other non-time inputs/choices,
registered scopes, exact hash referents, CA/leaf chain and key intervals are fixed.

| Source family / calls | Accepted set as a function of Now=n |
| --- | --- |
| trust.go NewVerifier | UTC/nonzero domain condition, constant over this allowed interval |
| temporal.go recordUse | n>=original signed consumingAt |
| proofs.go freshnessAt, all modes | n>=consumingAt; immutable original consuming validity checks are constants |
| publication status in freshnessAt | n>=PublishedAt, n>=CheckedAt, n<=CheckedAt+120s, n<ExpiresAt |
| native.go current certificate status | n>=CheckedAt, n<=CheckedAt+120s, n<ExpiresAt |
| trust.go keyAt reached with live use.at=n; key wrapper | NotBefore<=n<NotAfter; original observation/use times otherwise constant |
| native.go x509.Verify CurrentTime=n | For fixed leaf and sole exact CA with no alternate chain/intermediate source, intersection of NotBefore<=n<=NotAfter for certificates; all other chain/URI/EKU/signature checks constant |
| proofs.go fresh use.at=n | n>=observedAt-30s, n<=observedAt+min(planAge,120s), n<validUntil, n<planExpiry, acquiredAt<=n<operationExpiry |
| proofs.go verifyNativeAt live challenge | issuedAt<=n<challengeExpiry, with original observed/challenge relations constant; historical challenge comparisons use original consuming time, not n |
| current.go currentNativeWitnesses/currentReadback | Propagate n into the preceding fixed-input native/key/fresh/status predicates; derived until=min(original observation+age,leaf end,plan end,HELD end) is constant |
| verify.go VerifyCurrentProjectionSet | acquiredAt<=n<operationExpiry; n<signedLeaseExpiry; readback n<until, n>=observedAt-30s, n<=observedAt+120s |

Every row is a half-line, half-open/closed interval, or a fixed Boolean. Their
finite conjunction is convex: if both endpoints pass, every interior t0 passes.
Strict upper bounds are tested strictly; status age's120s endpoint is inclusive.
K1's zero/UTC domain condition and native certificate original-time conditions
are handled explicitly rather than assumed convex over all possible Time values.

The only apparent existential is finding a fresh CP head proof. All successful
candidates must name the SAME exact artifact raw hash and fixed contract/subject/
operation. The normalized signed raw body fixes observedAt and validUntil; a
different contract/body/time cannot authenticate under that hash. Thus candidates
do not supply disjoint time intervals. Original head lookup also requires one
unambiguous authenticated runtime-inventory identity. Native expected declarations
must agree, or K1 rejects before accepting current. No varying chain, signer,
record or proof is selected to bridge a failed interior interval.

On success K1's Report/classification/counts/digests and current set digest are
computed only from those fixed authenticated bytes/graph. Now gates acceptance,
not the successful digest value. The endpoint and returned-t0 output comparison
still remains mandatory; it does not rely solely on this reasoning.

## External primitive obligation and actual limitations

The locally available Go1.27.0 x509/verify.go source was read and hashed in
clock-stdlib-source-obligation.json. It uses explicit opts.CurrentTime, falls
back to time.Now only if zero, and rejects before NotBefore or after NotAfter.
This establishes the stated primitive semantics for that inspected source.
It is NOT a claim that future installed toolchain code (or K1 CI Go1.27.1) has
been byte-matched to it. The actual running entrypoint must bind its exact
toolchain/stdlib semantics and fixed-chain assumptions through independent
review/installation provenance. Missing that match keeps CLOCK_MECHANISM_HOLD
and ERR[CLOCK_MECHANISM_UNPROVEN]; no current or real history usability is claimed.

The focused new scratch source check at eb32 uses existing synthetic K1 fixtures:
positive endpoint full-output equality, exclusive publication expiry, exclusive
current key interval while historical use remains valid, inclusive120s status
age, and inclusive live challenge issue time. It does not execute the proposed
K2 clock adapter, prove an installed clock, or run any A01–A40 case. Additional
symbolic boundary cases in the inventory cover every listed interval family;
they are STATIC arithmetic checks, not substitute K1/runtime implementations.
