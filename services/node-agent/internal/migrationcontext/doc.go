// Package migrationcontext defines the read-only application boundary around K1.
//
// This revision deliberately has NO production authentication implementation.
// Independent provisioning and purpose-specific registry, archive, status, clock
// and running-code attestations have not been registered. NewService has null
// ports; even internally consistent, self-signed provider records are untrusted.
// No filename, digest, role label, provider declaration or callback installs trust.
// LoadInstalledPolicy, ReadHistory and ValidateHistory therefore cannot complete
// positively through the public service in this revision. Private synthetic test
// fixtures bypass this missing authentication ONLY to exercise downstream logic.
//
// Callers exclusively own input maps/slices during a call. Defensive copying
// severs aliases; it does not synchronize concurrent writes. Opaque values belong
// to one service and exact read versions. JSON cannot construct their bindings.
// A successful historical report would authenticate history, never authorize an
// effect or establish a current view. There are no current/effect APIs here.
//
// The sole K1 integration is k1_bridge.go. This package performs no file, network,
// process, database, clock observation, signing, installation or mutation I/O.
// Opacity and source gates constrain the reviewed program; they do not defend
// against malicious code already executing in the same process.
package migrationcontext
