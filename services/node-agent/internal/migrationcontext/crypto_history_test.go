package migrationcontext

// Only this TEST reads the public, ephemeral-key fixture. The JSON is NOT an
// authenticated K2 provider record. Decoding it directly into private facts is a
// deliberate test-only bypass of the absent external authentication boundary.
// No private keys are present; the exact exporter/source/hash are in Evidence.
import (
	"bytes"
	"encoding/json"
	"os"
	"testing"
	"time"
)

func syntheticCryptoHistory(t *testing.T) (policyData, historyData, statusData, clockEnvelope, UntrustedPacket) {
	t.Helper()
	raw, e := os.ReadFile("testdata/synthetic-public-history.json")
	if e != nil {
		t.Fatal(e)
	}
	var f struct {
		Classification string
		Installed      policyData
		Context        struct {
			Now                  time.Time
			SemanticInputs       any
			MigrationOperationID string
			History              struct {
				Operations map[string]operation
				Challenges map[string]challenge
			}
			Publications map[string]publicationStatus
			Certificates map[string]certificateStatus
		}
		Packet UntrustedPacket
	}
	d := json.NewDecoder(bytes.NewReader(raw))
	d.UseNumber()
	if e = d.Decode(&f); e != nil {
		t.Fatal(e)
	}
	if f.Classification != "SYNTHETIC TEST ONLY; NO PRIVATE KEYS; NO AUTHENTICATED K2 PRODUCER" {
		t.Fatal("fixture classification")
	}
	p := f.Installed
	p.Selector = "synthetic-export"
	p.Version = "SYNTHETIC-policy-v1"
	p.Provenance = provenance{ReviewTargetSHA: p.Verifier.SourceSHA, ReviewScope: "SYNTHETIC_ONLY", ApprovedReviewScope: "SYNTHETIC_ONLY", BinaryVCS: p.Verifier.SourceSHA, RuntimeLockSHA256: hx("1", 64), CIHeadSHA: p.Verifier.SourceSHA, CIRef: "SYNTHETIC", CIWorkflow: "SYNTHETIC", CIRunID: p.Verifier.CIRunIDs[0], CIAttempt: "1", CIJobID: "SYNTHETIC", ArtifactDigest: hx("2", 64), InstallationReceiptSHA256: hx("3", 64), RunningExecutableSHA256: p.Verifier.ArtifactSHA256, LinkedClosureSHA256: hx("4", 64)}
	op, ok := f.Context.History.Operations[f.Context.MigrationOperationID]
	if !ok {
		t.Fatal("original operation absent")
	}
	var lease []byte
	for _, m := range []map[string][]byte{f.Packet.Records, f.Packet.Referents} {
		for _, b := range m {
			if hashBytes(b) == op.LeaseEnvelopeSHA256 {
				lease = b
			}
		}
	}
	if len(lease) == 0 {
		t.Fatal("exact original HELD bytes absent")
	}
	plan := f.Context.SemanticInputs.(map[string]any)["plan"]
	planRaw, e := canonicalValue(plan)
	if e != nil {
		t.Fatal(e)
	}
	scope, e := cohortScopeHash(p)
	if e != nil {
		t.Fatal(e)
	}
	h := historyData{Query: HistoryQuery{CohortID: p.CohortID, ScopeSHA256: scope, Version: "SYNTHETIC-archive-v1", OriginalMigrationID: op.MigrationID, OriginalOperationID: op.OperationID, OriginalLeaseSHA256: op.LeaseEnvelopeSHA256, OriginalPlanBodySHA256: hashBytes(planRaw), ArchiveSHA256: hashBytes(raw), FenceEpoch: op.FenceEpoch}, PolicyVersion: p.Version, CurrentVersion: "SYNTHETIC-status-v1", SemanticInputs: f.Context.SemanticInputs, Operations: f.Context.History.Operations, Challenges: f.Context.History.Challenges, OriginalLease: lease, OriginalPlanBody: planRaw, ArchiveBytes: raw}
	st := statusData{PolicyVersion: p.Version, CurrentVersion: h.CurrentVersion, Publications: f.Context.Publications, Certificates: f.Context.Certificates}
	c := clockEnvelope{L: f.Context.Now, U: f.Context.Now.Add(200 * time.Millisecond), T0: f.Context.Now.Add(100 * time.Millisecond), PolicyVersion: p.Version, CurrentVersion: h.CurrentVersion, MechanismSourceSHA: hx("5", 40), StdlibSHA256: hx("6", 64), RunningClosureSHA256: p.Provenance.LinkedClosureSHA256, MappingVersion: "SYNTHETIC_NO_PRODUCTION_CLOCK", AcquisitionStart: 1, EvaluationStart: 2, Deadline: 20, EvaluationEnd: 10, MaxElapsedUncertainty: time.Second}
	return p, h, st, c, f.Packet
}

func TestAlreadyBoundSyntheticCryptoHistoryEndpoints(t *testing.T) {
	p, h, st, c, packet := syntheticCryptoHistory(t)
	// This positive only exercises downstream K1 and the interval wrapper. It
	// cannot mint a public service policy/history or validate a real producer.
	if !h.Operations[h.Query.OriginalOperationID].ExpiresAt.Before(c.L) {
		t.Fatal("expected expired ORIGINAL lease")
	}
	r, e := evaluateBoundHistory(p, h, st, c, packet)
	if e != nil {
		t.Fatal(e)
	}
	if r.RealSignatures == 0 || r.Records == 0 || len(r.Digests) == 0 {
		t.Fatal("no actual K1 crypto work")
	}
	t.Logf("SYNTHETIC auth bypass only: L/U/t0 full-report equal, records=%d proofs=%d signatures=%d", r.Records, r.ProofReferences, r.RealSignatures)
	for _, m := range []struct {
		name   string
		mutate func(*policyData, *historyData, *statusData, *clockEnvelope, *UntrustedPacket)
		code   Code
	}{
		{"current-selector", func(_ *policyData, h *historyData, _ *statusData, _ *clockEnvelope, _ *UntrustedPacket) {
			h.Query.OriginalOperationID = "CURRENT-is-not-original"
		}, OriginalOperationMismatch},
		{"publication-revoked", func(_ *policyData, _ *historyData, s *statusData, _ *clockEnvelope, _ *UntrustedPacket) {
			for k, v := range s.Publications {
				v.Status = "REVOKED"
				s.Publications[k] = v
				break
			}
		}, PublicationUnknown},
		{"certificate-revoked", func(_ *policyData, _ *historyData, s *statusData, _ *clockEnvelope, _ *UntrustedPacket) {
			for k, v := range s.Certificates {
				v.Status = "REVOKED"
				s.Certificates[k] = v
				break
			}
		}, CertificateUnknown},
		{"upper-endpoint-expiry", func(_ *policyData, _ *historyData, s *statusData, c *clockEnvelope, _ *UntrustedPacket) {
			for k, v := range s.Publications {
				v.ExpiresAt = c.U
				s.Publications[k] = v
				break
			}
		}, PublicationUnknown},
		{"raw-proof-corruption", func(_ *policyData, _ *historyData, _ *statusData, _ *clockEnvelope, p *UntrustedPacket) {
			for k, v := range p.Referents {
				v = copyBytes(v)
				v[len(v)-1] ^= 1
				p.Referents[k] = v
			}
		}, K1Refused},
	} {
		t.Run(m.name, func(t *testing.T) {
			p, h, st, c, pkt := syntheticCryptoHistory(t)
			m.mutate(&p, &h, &st, &c, &pkt)
			_, e := evaluateBoundHistory(p, h, st, c, pkt)
			wantCode(t, e, m.code)
		})
	}
}

func TestAlreadyBoundPolicyJoinsDoNotAuthenticate(t *testing.T) {
	p, _, _, _, _ := syntheticCryptoHistory(t)
	r := runningData{ExecutableSHA256: p.Verifier.ArtifactSHA256, InstallationReceiptSHA256: p.Provenance.InstallationReceiptSHA256, SourceSHA: p.Verifier.SourceSHA, RuntimeLockSHA256: p.Provenance.RuntimeLockSHA256, LinkedClosureSHA256: p.Provenance.LinkedClosureSHA256}
	if e := checkPolicyBindings(p, r); e != nil {
		t.Fatal(e)
	}
	wantCode(t, authenticateRegistry(registryRecord{data: p}), TrustUnknown)
	for _, m := range []struct {
		name   string
		mutate func(*policyData, *runningData)
		code   Code
	}{
		{"wrong-executable", func(_ *policyData, r *runningData) { r.ExecutableSHA256 = hx("f", 64) }, RunningIdentityMismatch},
		{"archive-is-not-executable", func(p *policyData, r *runningData) { r.ExecutableSHA256 = p.Provenance.ArtifactDigest }, RunningIdentityMismatch},
		{"review-scope", func(p *policyData, _ *runningData) { p.Provenance.ReviewScope = "different" }, TrustUnknown},
		{"review-target", func(p *policyData, _ *runningData) { p.Provenance.ReviewTargetSHA = hx("f", 40) }, TrustUnknown},
		{"ci-run", func(p *policyData, _ *runningData) { p.Provenance.CIRunID = "other" }, TrustUnknown},
		{"wrong-node-DER", func(p *policyData, _ *runningData) {
			p.Members[0].CertificateDER = copyBytes(p.Members[1].CertificateDER)
		}, TrustUnknown},
		{"wrong-node-grant", func(p *policyData, _ *runningData) {
			for i, g := range p.Grants {
				if g.Role == "node-leaf" {
					p.Grants[i].PublicKeyHex = hx("f", 64)
				}
			}
		}, TrustUnknown},
	} {
		t.Run(m.name, func(t *testing.T) {
			f, e := freezePolicy(p)
			if e != nil {
				t.Fatal(e)
			}
			measured := r
			m.mutate(&f, &measured)
			wantCode(t, checkPolicyBindings(f, measured), m.code)
		})
	}
}
