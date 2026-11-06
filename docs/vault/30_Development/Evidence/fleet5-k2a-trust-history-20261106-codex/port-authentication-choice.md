# Concrete authentication boundary before provider implementations

Source: exact4ce63e8e/eb32 product; Root code grant msg_18271633c26c.

The grant requires port records to remain untrusted until checked factories
authenticate registry/grants/publication/review/source/installation/running-code
and current history/status/clock bindings. It also forbids unchecked callback
or boolean-auth escapes, new accepted wire/descriptor/key/domain and production
provider implementations. Current trusted-root deployment bindings are all null
in migrationverify/resources/trust-bootstrap-contract.json. The28 existing
proof kinds do not define a complete sealed-registry, archive read snapshot,
status-source, clock observation or running-code provider attestation format.
The g2-planning-policy approval of a registry digest is not a trust-installation
receipt; a valid Node/CA signature is not an operator registry approval.

Counterexample: a fake RegistryPort returns a correctly shaped registry whose
hash matches its own metadata, plus ACTIVE role labels, accepted=true and a new
self-issued seal key. A format/hash/label-only factory would accept untrusted
authority, violating the grant. Calling a provider's verify=true callback would
merely relocate the same unchecked assertion.

Candidate A (strict missing-format HOLD): no production authentication codec is
introduced. Ports/default refusals and checked binding/freeze/clock/K1 bridge
logic exist, but unregistered attestation purpose/format cannot create a policy.
Package-internal tests may construct explicitly synthetic already-bound private
fixtures to test downstream binding/clock/K1/refusals; this does not claim a
positive production registry authenticator or installation. A future separately
reviewed composition/attestation contract is required for real positive factories.

Candidate B (explicitly approved private verification seam): factories may verify
an in-memory typed record with genuine signatures against private independently
preapproved purpose-scoped public anchors and exact binding/provenance policy.
No caller/public constructor supplies roots/providers/Now; NewService starts with
null ports. All positive source records/keys are synthetic test-only fixtures.
The authentication byte/message binding must be specified by Root or remain an
unregistered format/HOLD; it is not inferred from existing K1 proof kinds.

The question is the exact positive authentication seam permitted by this code
grant, not permission to read keys, provision trust, install a source or execute
effects. Independent source/shape/boundary gate work does not need that choice.


## Actual Root decision

Root msg_f4259ea0de6b answered CHOOSE A, narrowing msg_18271633c26c under the
same actual task/dispatch. Candidate B above is historical question context only;
it is not granted or implemented. Public positive authentication is not granted.
The current code deliberately refuses every unregistered registry/archive/status/
clock/running-code format. Private already-bound synthetic test fixtures may
exercise downstream pure logic and the K1 bridge. They cannot issue a public
opaque input or represent a real registered producer. The actual dependency is a
separately closed/reviewed independent provisioning and attestation-verification
contract per purpose, registered anchors/ports and a future explicit Root grant.
