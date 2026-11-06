package migrationcontext

import (
	"crypto/ed25519"
	"crypto/rand"
	"encoding/json"
	"errors"
	"strings"
	"testing"
	"time"
)

func wantCode(t *testing.T, err error, c Code) {
	t.Helper()
	var r *Refusal
	if !errors.As(err, &r) || r.Code() != c {
		t.Fatalf("got %v, want %s", err, c)
	}
}
func hx(s string, n int) string { return strings.Repeat(s, n) }

// ALREADY-BOUND SYNTHETIC fixtures deliberately bypass missing external auth.
// Only downstream binding/copy/selector logic is exercised. No producer, trust
// installation, live observation, deployment or A01-A40 execution is proved.
func synthetic(t *testing.T) (*Service, *InstalledPolicy, *History, clockEnvelope, statusData, runningData) {
	t.Helper()
	s := NewService()
	at := time.Date(2030, 1, 2, 3, 4, 5, 0, time.UTC)
	p := policyData{Selector: "synthetic-deployment", Version: "policy-v1", RegistrySHA256: hx("1", 64), Verifier: publication{ID: "saintvision-migrationverify-k1:1", SourceSHA: hx("2", 40), ArtifactSHA256: hx("3", 64), ReviewSHA: hx("4", 40), CIRunIDs: []string{"synthetic-run"}}, CohortID: "synthetic-old-two", GraphBytes: []byte("synthetic graph"), ContractPins: map[string]contractPin{"synthetic": {Codec: "synthetic"}}, NodeKinds: map[string]string{"plan": "successor-plan"}, Grants: []grant{{Role: "synthetic", AuthorityScope: map[string]any{"class": "COHORT"}, PublicKeyHex: hx("5", 64), NotBefore: at.Add(-time.Hour), NotAfter: at.Add(time.Hour), Status: "ACTIVE"}}, Provenance: provenance{ReviewTargetSHA: hx("2", 40), ReviewScope: "synthetic scope", ApprovedReviewScope: "synthetic scope", BinaryVCS: hx("2", 40), RuntimeLockSHA256: hx("6", 64), CIHeadSHA: hx("2", 40), CIRef: "synthetic-ref", CIWorkflow: "synthetic-workflow", CIRunID: "synthetic-run", CIAttempt: "1", CIJobID: "synthetic-job", ArtifactDigest: hx("7", 64), InstallationReceiptSHA256: hx("8", 64), RunningExecutableSHA256: hx("3", 64), LinkedClosureSHA256: hx("9", 64)}}
	for _, slot := range []string{"PC2", "PC4"} {
		p.Members = append(p.Members, member{Slot: slot, Scope: map[string]any{"tenantId": "synthetic-tenant", "nodeId": slot, "recoveryEpoch": "synthetic-epoch"}, CertificateDER: []byte("synthetic-not-a-certificate"), CARootDER: []byte("synthetic-not-a-ca")})
	}
	p.GraphSHA256 = hashBytes(p.GraphBytes)
	lease := []byte("synthetic exact original HELD bytes")
	plan := map[string]any{"expiresAt": "2030-01-03T00:00:00Z", "maxEvidenceAgeSeconds": json.Number("120")}
	planRaw, e := canonicalValue(plan)
	if e != nil {
		t.Fatal(e)
	}
	scope, e := cohortScopeHash(p)
	if e != nil {
		t.Fatal(e)
	}
	h := historyData{Query: HistoryQuery{CohortID: p.CohortID, ScopeSHA256: scope, Version: "archive-v1", OriginalMigrationID: "migration-old", OriginalOperationID: "operation-old", OriginalLeaseSHA256: hashBytes(lease), OriginalPlanBodySHA256: hashBytes(planRaw), ArchiveSHA256: hashBytes([]byte("archive snapshot")), FenceEpoch: 1}, PolicyVersion: p.Version, CurrentVersion: "status-v1", SemanticInputs: map[string]any{"plan": plan, "facts": map[string]any{"migrationOperationId": "operation-old", "containers": map[string]any{"current": "ORIGINAL epoch1, not runtime"}}}, Operations: map[string]operation{"operation-old": {MigrationID: "migration-old", OperationID: "operation-old", LeaseEnvelopeSHA256: hashBytes(lease), FenceEpoch: 1, AcquiredAt: at.Add(-2 * time.Hour), ExpiresAt: at.Add(-time.Hour)}}, OriginalLease: lease, OriginalPlanBody: planRaw, ArchiveBytes: []byte("archive snapshot")}
	pf, e := freezePolicy(p)
	if e != nil {
		t.Fatal(e)
	}
	pd, e := policyDigest(pf)
	if e != nil {
		t.Fatal(e)
	}
	op := &InstalledPolicy{binding: &policyBinding{owner: s, version: p.Version, digest: pd, data: pf}}
	hf, e := freezeHistory(h)
	if e != nil {
		t.Fatal(e)
	}
	hd, e := historyDigest(hf)
	if e != nil {
		t.Fatal(e)
	}
	oh := &History{binding: &historyBinding{owner: s, policyDigest: pd, digest: hd, data: hf}}
	c := clockEnvelope{L: at.Add(-100 * time.Millisecond), U: at.Add(100 * time.Millisecond), T0: at, PolicyVersion: p.Version, CurrentVersion: h.CurrentVersion, MechanismSourceSHA: hx("a", 40), StdlibSHA256: hx("b", 64), RunningClosureSHA256: p.Provenance.LinkedClosureSHA256, MappingVersion: "SYNTHETIC-ONLY", AcquisitionStart: 1, EvaluationStart: 10, Deadline: 30, EvaluationEnd: 20, MaxElapsedUncertainty: time.Second}
	st := statusData{PolicyVersion: p.Version, CurrentVersion: h.CurrentVersion, Publications: map[string]publicationStatus{hx("c", 64): {Status: "ACCEPTED_UNREVOKED", SubjectSHA256: hx("d", 64), PublishedAt: at.Add(-time.Hour), CheckedAt: at.Add(-time.Second), ExpiresAt: at.Add(time.Hour)}}, Certificates: map[string]certificateStatus{hx("e", 64): {Status: "UNREVOKED", CheckedAt: at.Add(-time.Second), ExpiresAt: at.Add(time.Hour)}}}
	r := runningData{ExecutableSHA256: p.Verifier.ArtifactSHA256, InstallationReceiptSHA256: p.Provenance.InstallationReceiptSHA256, SourceSHA: p.Verifier.SourceSHA, RuntimeLockSHA256: p.Provenance.RuntimeLockSHA256, LinkedClosureSHA256: p.Provenance.LinkedClosureSHA256}
	return s, op, oh, c, st, r
}

type fakeRegistry struct {
	record registryRecord
	calls  int
}

func (f *fakeRegistry) readRegistry(string) (registryRecord, error) { f.calls++; return f.record, nil }

type fakeArchive struct {
	record archiveRecord
	calls  int
}

func (f *fakeArchive) readHistory(historyRequest) (archiveRecord, error) {
	f.calls++
	return f.record, nil
}

type fakeRunning struct {
	record runningRecord
	calls  int
}

func (f *fakeRunning) readRunningCode() (runningRecord, error) { f.calls++; return f.record, nil }

func TestNullPortsAndOpaqueBoundary(t *testing.T) {
	s := NewService()
	wantCode(t, s.checkClockSource(), ClockUntrusted)
	wantCode(t, s.checkPublicationSource("version"), PublicationUnknown)
	wantCode(t, s.checkCertificateSource("version"), CertificateUnknown)
	p, e := s.LoadInstalledPolicy("deployment")
	if p != nil {
		t.Fatal("issued policy")
	}
	wantCode(t, e, TrustUnknown)
	_, e = s.ReadHistory(&InstalledPolicy{}, HistoryQuery{})
	wantCode(t, e, TrustUnknown)
	_, e = s.ValidateHistory(UntrustedPacket{}, &InstalledPolicy{}, &History{})
	wantCode(t, e, TrustUnknown)
	s, p, h, _, _, _ := synthetic(t)
	_, e = s.ReadHistory(p, h.binding.data.Query)
	wantCode(t, e, HistoryUnknown)
	_, e = s.ValidateHistory(UntrustedPacket{}, p, h)
	wantCode(t, e, InstallationUnknown)
	foreign := NewService()
	_, e = foreign.ValidateHistory(UntrustedPacket{}, p, h)
	wantCode(t, e, TrustUnknown)
	var forged InstalledPolicy
	if e = json.Unmarshal([]byte(`{"binding":{"version":"policy-v1"},"RegistrySHA256":"1"}`), &forged); e != nil {
		t.Fatal(e)
	}
	wantCode(t, s.checkPolicy(&forged), TrustUnknown)
	var forgedHistory History
	if e = json.Unmarshal([]byte(`{"binding":{"digest":"x"}}`), &forgedHistory); e != nil {
		t.Fatal(e)
	}
	wantCode(t, s.checkHistory(p, &forgedHistory), HistoryUnknown)
	wantCode(t, s.checkHistory(nil, h), TrustUnknown)
	p.binding.version = "other"
	wantCode(t, s.checkPolicy(p), TrustUnknown)
}

func TestWellFormedUnregisteredProvidersNeverAuthenticate(t *testing.T) {
	s, p, h, c, st, r := synthetic(t)
	_, key, e := ed25519.GenerateKey(rand.Reader)
	if e != nil {
		t.Fatal(e)
	}
	// A real self-issued signature is still NOT an authorized purpose/anchor.
	evidence := providerEvidence{purpose: "unregistered", format: "self-issued", version: "1", raw: ed25519.Sign(key, []byte("consistent provider bytes"))}
	rg := &fakeRegistry{record: registryRecord{evidence: evidence, data: p.binding.data}}
	s.registry = rg
	got, e := s.LoadInstalledPolicy("synthetic-deployment")
	if got != nil || rg.calls != 1 {
		t.Fatal("registry boundary")
	}
	wantCode(t, e, TrustUnknown)
	for _, bad := range []string{"../registry", "C:\\registry", "file://registry", "/registry"} {
		_, e = s.LoadInstalledPolicy(bad)
		wantCode(t, e, TrustUnknown)
	}
	if rg.calls != 1 {
		t.Fatal("path reached provider")
	}
	ar := &fakeArchive{record: archiveRecord{evidence: evidence, data: h.binding.data}}
	s.archive = ar
	hist, e := s.ReadHistory(p, h.binding.data.Query)
	if hist != nil || ar.calls != 1 {
		t.Fatal("archive boundary")
	}
	wantCode(t, e, HistoryUnknown)
	wrongScope := h.binding.data.Query
	wrongScope.ScopeSHA256 = hx("f", 64)
	_, e = s.ReadHistory(p, wrongScope)
	wantCode(t, e, OriginalOperationMismatch)
	if ar.calls != 1 {
		t.Fatal("foreign scope reached archive")
	}
	run := &fakeRunning{record: runningRecord{evidence: evidence, data: r}}
	s.running = run
	_, e = s.ValidateHistory(UntrustedPacket{}, p, h)
	wantCode(t, e, InstallationUnknown)
	if run.calls != 1 {
		t.Fatal("running boundary")
	}
	wantCode(t, authenticateStatus(statusRecord{evidence: evidence, data: st}), PublicationUnknown)
	wantCode(t, authenticateCertificateStatus(statusRecord{evidence: evidence, data: st}), CertificateUnknown)
	wantCode(t, authenticateClock(clockRecord{evidence: evidence, data: c}), ClockUntrusted)
}

func TestAlreadyBoundSyntheticOriginalSelectorAndFreeze(t *testing.T) {
	s, p, h, _, _, r := synthetic(t)
	if e := s.checkPolicy(p); e != nil {
		t.Fatal(e)
	}
	if e := s.checkHistory(p, h); e != nil {
		t.Fatal(e)
	}
	_ = r // This simple fixture deliberately has no DER and is not policy-authenticated.
	// Original operation is expired and no live map even exists in this package.
	for _, mutation := range []func(*historyData){func(h *historyData) { h.Query.OriginalOperationID = "operation-current" }, func(h *historyData) { delete(h.Operations, "operation-old") }, func(h *historyData) {
		h.SemanticInputs.(map[string]any)["facts"].(map[string]any)["migrationOperationId"] = "operation-current"
	}, func(h *historyData) { h.Query.FenceEpoch = 2 }, func(h *historyData) { h.OriginalLease[0] ^= 1 }, func(h *historyData) { h.OriginalPlanBody[0] ^= 1 }, func(h *historyData) { h.Query.ScopeSHA256 = hx("f", 64) }} {
		f, e := freezeHistory(h.binding.data)
		if e != nil {
			t.Fatal(e)
		}
		mutation(&f)
		wantCode(t, checkOriginalHistory(p.binding.data, f), OriginalOperationMismatch)
	}
	f, e := freezeHistory(h.binding.data)
	if e != nil {
		t.Fatal(e)
	}
	f.OriginalLease[0] ^= 1
	f.Operations["operation-old"] = operation{}
	f.SemanticInputs.(map[string]any)["facts"].(map[string]any)["containers"].(map[string]any)["current"] = "wrong runtime"
	if e = s.checkHistory(p, h); e != nil {
		t.Fatal("alias escaped", e)
	}
	p.binding.data.GraphBytes[0] ^= 1
	wantCode(t, s.checkPolicy(p), TrustUnknown)
	s, p, h, _, _, _ = synthetic(t)
	h.binding.data.ArchiveBytes[0] ^= 1
	wantCode(t, s.checkHistory(p, h), HistoryUnknown)
}

type hostileMarshaler struct{ called *bool }

func (x hostileMarshaler) MarshalJSON() ([]byte, error) { *x.called = true; return []byte(`{}`), nil }
func TestCopyRejectsCallbacksAndBoundsBeforeEncoding(t *testing.T) {
	called := false
	_, e := cloneJSON(map[string]any{"hostile": hostileMarshaler{&called}})
	wantCode(t, e, HistoryUnknown)
	if called {
		t.Fatal("unchecked callback executed")
	}
	for _, v := range []any{func() {}, json.Number("null"), json.Number("[1]"), json.Number("01"), "\xff"} {
		_, e = cloneJSON(v)
		wantCode(t, e, HistoryUnknown)
	}
	var deep any = nil
	for i := 0; i < 70; i++ {
		deep = []any{deep}
	}
	_, e = cloneJSON(deep)
	wantCode(t, e, HistoryUnknown)
	p := UntrustedPacket{Records: map[string][]byte{"x": []byte("original")}}
	f, e := freezePacket(p)
	if e != nil {
		t.Fatal(e)
	}
	p.Records["x"][0] = 'X'
	if string(f.Records["x"]) != "original" {
		t.Fatal("packet alias")
	}
}

func TestAlreadyBoundCurrentStatusAgeAndRefusalIsolation(t *testing.T) {
	_, p, h, c, st, _ := synthetic(t)
	for k, v := range st.Publications {
		v.CheckedAt = c.T0.Add(-120 * time.Second)
		st.Publications[k] = v
	}
	if e := checkStatusBindings(p.binding.data, h.binding.data, st, c.T0); e != nil {
		t.Fatal("inclusive 120s boundary", e)
	}
	wantCode(t, checkStatusBindings(p.binding.data, h.binding.data, st, c.T0.Add(time.Nanosecond)), PublicationUnknown)
	_, p, h, c, st, _ = synthetic(t)
	for k, v := range st.Publications {
		v.CheckedAt = c.T0.Add(time.Nanosecond)
		st.Publications[k] = v
	}
	wantCode(t, checkStatusBindings(p.binding.data, h.binding.data, st, c.T0), PublicationUnknown)
	_, p, h, c, st, _ = synthetic(t)
	st.Publications = nil
	wantCode(t, checkStatusBindings(p.binding.data, h.binding.data, st, c.T0), PublicationUnknown)
	_, p, h, c, st, _ = synthetic(t)
	st.Certificates = nil
	wantCode(t, checkStatusBindings(p.binding.data, h.binding.data, st, c.T0), CertificateUnknown)
	_, p, h, c, st, _ = synthetic(t)
	for k, v := range st.Certificates {
		v.ExpiresAt = c.T0
		st.Certificates[k] = v
	}
	wantCode(t, checkStatusBindings(p.binding.data, h.binding.data, st, c.T0), CertificateUnknown)
	_, p, h, c, st, _ = synthetic(t)
	st.CurrentVersion = "other-migration-version"
	wantCode(t, checkStatusBindings(p.binding.data, h.binding.data, st, c.T0), StaleSnapshot)
}

func TestSyntheticClockEnvelopeAndCompleteOutput(t *testing.T) {
	_, p, h, c, st, _ := synthetic(t)
	if e := checkClock(p.binding.data, h.binding.data, c); e != nil {
		t.Fatal(e)
	}
	for _, m := range []func(*clockEnvelope){func(c *clockEnvelope) { c.L = time.Time{} }, func(c *clockEnvelope) { c.U = c.L.Add(-time.Nanosecond) }, func(c *clockEnvelope) { c.T0 = c.U.Add(time.Nanosecond) }, func(c *clockEnvelope) { c.L = c.L.In(time.FixedZone("non-UTC", 0)) }, func(c *clockEnvelope) { c.U = c.L.Add(time.Second + time.Nanosecond) }, func(c *clockEnvelope) { c.EvaluationEnd = c.Deadline + 1 }, func(c *clockEnvelope) { c.MaxElapsedUncertainty = 30 * time.Second }, func(c *clockEnvelope) {
		c.L = time.Time{}.Add(-time.Nanosecond)
		c.U = time.Time{}.Add(time.Nanosecond)
		c.T0 = c.U
	}} {
		f := c
		m(&f)
		wantCode(t, checkClock(p.binding.data, h.binding.data, f), ClockIntervalInvalid)
	}
	f := c
	f.StdlibSHA256 = ""
	wantCode(t, checkClock(p.binding.data, h.binding.data, f), ClockMechanismUnproven)
	f = c
	f.CurrentVersion = "new-version"
	wantCode(t, checkClock(p.binding.data, h.binding.data, f), StaleSnapshot)
	a := HistoryReport{Classification: "history-only", Records: 2, ProofReferences: 3, RealSignatures: 4, Digests: map[string]string{"x": "one"}}
	b := a
	b.Digests = copyMap(a.Digests)
	if !reportsEqual(a, b) {
		t.Fatal("equal reports")
	}
	b.RealSignatures++
	if reportsEqual(a, b) {
		t.Fatal("omitted count")
	}
	b = a
	b.Digests = map[string]string{"y": "one"}
	if reportsEqual(a, b) {
		t.Fatal("omitted digest key")
	}
	if e := checkStatusBindings(p.binding.data, h.binding.data, st, c.T0); e != nil {
		t.Fatal(e)
	}
	for key, x := range st.Publications {
		x.ExpiresAt = c.U
		st.Publications[key] = x
	}
	wantCode(t, checkStatusBindings(p.binding.data, h.binding.data, st, c.U), PublicationUnknown)
	// Invalid synthetic graph/certs must reach a CLOSED K1 refusal; no raw error
	// or partial report escapes. This is not a positive producer/crypto proof.
	_, e := evaluateBoundHistory(p.binding.data, h.binding.data, st, c, UntrustedPacket{})
	wantCode(t, e, K1Refused)
}
