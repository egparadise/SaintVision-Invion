# Migration verifier K1

This package verifies supplied immutable inputs offline. It has no operational
adapter, CLI, filesystem publication, clock reader, runtime import or migration
admission output. K2 must provide actual installed trust and authenticated current
observations before any integration can use it. No live registration exists here.

The original design is source `8874b2dfe0dda9a019bd5f334636668290702e13`, reviewed
at `6b12d3ab0e1f3e3cf623b62c528e0e096ba48af6`. The 17 original schema blobs and
11 inputs remain byte-exact, with their source and package paths in
`resources/source-pins.json`. Seven schemas lacking `$id` are registered under
explicit resource IDs. Compilation never resolves a network resource. Only the
eight patterns in this pinned closure are supported; literal ECMA Unicode NUL
escapes are translated into equivalent RE2 notation without changing the files.

`resources/proposed-contracts` is a **new wire proposal requiring actual code and
contract review**, authorized by Root decision
`6e3fc79c22886a7d4424b7831871ce6ed1597d48`. It contains 28 exact contract/schema
descriptors and raw hashes. It does not fill the old registry's NULL deployment
bindings or install those proposals as live contracts.

## Trust boundary

`NewVerifier(InstalledTrust, TrustedContext)` takes two **trusted application
inputs** independently of `Packet`. A packet supplies only serialized records and
exact referenced bytes. It cannot supply a key, grant, verifier, schema, digest
algorithm, callback, clock override or fallback mode. There are no test adapters
or fixture-policy flags in the production API.

K1 performs structural validation of supplied installation/publication/context
bindings and exact local descriptor/schema lookup. It cannot establish that a
caller actually obtained those inputs from a reviewed installed registry, checked
the running verifier artifact against CI/review, or observed a host. Those are
mandatory K2 integration obligations. Passing untrusted packet metadata into
either trusted argument would violate this API contract. Provenance-shaped
strings supplied by an untrusted caller are not proof of an installation.

Required external data includes exact verifier source/artifact/CI/review and
contract/schema/codec pins, current scoped key grants, the complete ordered cohort,
actual unchanged Node certificate/CA DER, independently pinned graph and semantic
sources, actual trusted UTC time, authenticated operation/lease bindings, current
publication/nonrevocation decisions and member/operation/epoch-bound challenges.
Missing, NULL, unknown, revoked, mismatched or expired required data blocks an
authenticated output. `InstalledTrust` and `TrustedContext` maps/slices are copied;
one verifier can be used concurrently with immutable packets.

## Verification and bytes

Readers reject duplicate keys, invalid UTF8/surrogates, non-integer numeric tokens
(including `-0`, decimal/exponent forms), unsafe integers and trailing data. Closed
schemas reject foreign fields. Strings follow the pinned field rules, including
NUL rejection. UTC timestamps additionally undergo real calendar parsing and exact
whole-second roundtrip. C2 is Go map JSON: sorted keys, HTML/U+2028/U+2029 escaping,
raw other valid Unicode, no NFC and no body LF. Ordered argv JSON uses its separate
raw Unicode/HTML contract. Packet sizes and expression depth are bounded.

Original signatures and exact role/scope/key authorization authenticate before
any derived cohort digest is evaluated. Strict Ed25519 adds canonical on-curve
prime-order nonidentity A/R and `S<L` checks to the standard verification equation.
Key identities hash canonical Ed25519 PKIX/SPKI DER, never PEM or raw key bytes.

All 77 fixed slots use typed recipes derived from their actual containing source
and independent scoped facts. The graph deliberately strips proof references;
the separate proof layer validates their keys, roles, subjects, contracts, raw
bytes, freshness and operation binding. DAG evaluation uses dependency order,
rejects cycles/missing/duplicate rules, and covers each non-proof leaf exactly
once. API:2 Node and cohort prior references retain their distinct meanings.

Normalized proofs use the exact domain plus one NUL plus C2 of
`{body,signer:{role,keySPKISHA256}}`. Their raw bytes must equal C2 of the complete
envelope. Native M2 retains its original flat wire, domain and signed Unix seconds;
its raw artifact hash includes a transport LF when supplied. No codec fallback or
normalized re-signing of native evidence is possible.

Fresh, validity-bounded approval and immutable provenance semantics remain
distinct. Archival provenance has no operation fields and requires its original
publication validity plus current accepted publication/nonrevocation state.
Approvals have no 120-second age requirement and bind their original reduced-plan
or G2 subject. Fresh proofs bind the consuming migration/operation/lease and the
120-second age cap and 30-second future-skew cap.

Native reference validity is explicitly a **verified derived bound**, never a
Node-signed claim: the minimum of observation+age cap, certificate NotAfter floored
to seconds, plan expiry and current lease expiry. Current native use also requires
the external operation/member/epoch challenge. Host daemon/container/ExecID joins
are supplied through their separate scoped host proof contracts.

`Verify` returns authenticated offline history, never operational authorization.
Historical original HELD leases/challenges are separately supplied in
`TrustedContext.History`. Freshness and key authorization apply at the signed
containing record's time (or its exact causal signed event), with the original
lease window. Current external publication/nonrevocation still uses trusted Now.
The API does not backdate Now or turn historical verification into live admission.

`VerifyCurrentProjectionSet` additionally matches both original Node projections,
current lease/fence, complete member order and authenticated CP head/readback to
the independent current context before returning derived data. Epoch 1 RELEASED
and epoch 2 restore HELD remain distinct. `AuthenticateNativeHistory` returns a
separate immutable historical type with no fresh expiry, nonce admission or lease;
it cannot replace current verification.

The selected current lease must be the exact independently pinned HELD lease;
same-operation RELEASED history, a higher fence epoch of the registered cohort,
and a nonmaximal authenticated event sequence reject an obsolete view. Current
head readback is reverified at Now. Both ordered `Current.NativeWitnesses` contain
original producer bytes verified separately at Now against the current scoped
operation/epoch/nonce, expected state and the unchanged 120-second age bound.
Historical receipts do not automatically fill these current witness slots.

Current derivation requires a PRESENT authenticated inventory head. An ABSENT
pre-publication head fails closed without a current view; `Verify` still
authenticates history. K2 must independently authenticate producers of current
and historical contexts and enforce cohort fencing across migrations.

Each packet verification takes one bounded map/byte snapshot and uses it for all
hashes, parsing, native raw identity and returned authentication data. Callers
must own maps/slices without concurrent mutation during the call; a defensive
copy is not synchronization. Constructor inputs, including witness bytes, are
also copied. Immutable callers may share a verifier concurrently.

## Tests and remaining work

The original 195 objects are shape/byte fixtures with dummy signatures. Tests
regenerate separately labeled packets using ephemeral in-memory TEST keys and
certificates, real signatures and dependent rebindings. The original 112 proof
references cover 75 slots; additional test-only optional proofs cover the remaining
two slots and all 28 contract codecs. Public vectors contain no private keys.

K1 does not implement reservation, locking, replay/CAS, durable journals, Engine,
replacement, publication, rollback, runtime M2 collection, trust installation or
the 40 future bootstrap runtime acceptance cases. Those remain separate K2 or
operational work. This package does not connect to or change any physical Node.
