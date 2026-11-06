package migrationcontext

import (
	"crypto/ed25519"
	"crypto/rand"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/hex"
	"math/big"
	"net/url"
	"testing"
	"time"
)

func measuredFor(p policyData) runningData {
	return runningData{ExecutableSHA256: p.Verifier.ArtifactSHA256, InstallationReceiptSHA256: p.Provenance.InstallationReceiptSHA256, SourceSHA: p.Verifier.SourceSHA, RuntimeLockSHA256: p.Provenance.RuntimeLockSHA256, LinkedClosureSHA256: p.Provenance.LinkedClosureSHA256}
}

func TestReviewR2DistinctMemberBindings(t *testing.T) {
	p, _, _, _, _ := syntheticCryptoHistory(t)
	if e := checkPolicyBindings(p, measuredFor(p)); e != nil {
		t.Fatal(e)
	}
	t.Run("duplicate-scope-and-DER", func(t *testing.T) {
		f, e := freezePolicy(p)
		if e != nil {
			t.Fatal(e)
		}
		f.Members[1] = f.Members[0]
		f.Members[1].Slot = "PC4"
		wantCode(t, checkPolicyBindings(f, measuredFor(f)), TrustUnknown)
	})
	t.Run("duplicate-canonical-scope", func(t *testing.T) {
		f, e := freezePolicy(p)
		if e != nil {
			t.Fatal(e)
		}
		f.Members[1].Scope, e = cloneJSON(f.Members[0].Scope)
		if e != nil {
			t.Fatal(e)
		}
		wantCode(t, checkPolicyBindings(f, measuredFor(f)), TrustUnknown)
	})
	t.Run("duplicate-leaf-DER", func(t *testing.T) {
		f, e := freezePolicy(p)
		if e != nil {
			t.Fatal(e)
		}
		f.Members[1].CertificateDER = copyBytes(f.Members[0].CertificateDER)
		wantCode(t, checkPolicyBindings(f, measuredFor(f)), TrustUnknown)
	})
	t.Run("distinct-scope-DER-same-SPKI", func(t *testing.T) {
		// TEST ONLY ephemeral CA/leaf keys in memory. Two different valid Node
		// certificates/scopes share the same public key; bindings must reject it.
		f, e := freezePolicy(p)
		if e != nil {
			t.Fatal(e)
		}
		at := time.Date(2030, 1, 1, 0, 0, 0, 0, time.UTC)
		caPub, caKey, e := ed25519.GenerateKey(rand.Reader)
		if e != nil {
			t.Fatal(e)
		}
		leafPub, _, e := ed25519.GenerateKey(rand.Reader)
		if e != nil {
			t.Fatal(e)
		}
		ca := &x509.Certificate{SerialNumber: big.NewInt(1), Subject: pkix.Name{CommonName: "SYNTHETIC ONLY"}, NotBefore: at.Add(-time.Hour), NotAfter: at.Add(time.Hour), IsCA: true, BasicConstraintsValid: true, KeyUsage: x509.KeyUsageCertSign}
		caDER, e := x509.CreateCertificate(rand.Reader, ca, ca, caPub, caKey)
		if e != nil {
			t.Fatal(e)
		}
		for i := range f.Members {
			sc := f.Members[i].Scope.(map[string]any)
			uri, e := url.Parse("spiffe://saintvision.ai/tenant/" + sc["tenantId"].(string) + "/node/" + sc["nodeId"].(string) + "/epoch/" + sc["recoveryEpoch"].(string))
			if e != nil {
				t.Fatal(e)
			}
			cert := &x509.Certificate{SerialNumber: big.NewInt(int64(i + 2)), NotBefore: at.Add(-time.Hour), NotAfter: at.Add(time.Hour), URIs: []*url.URL{uri}, KeyUsage: x509.KeyUsageDigitalSignature, ExtKeyUsage: []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth}}
			der, e := x509.CreateCertificate(rand.Reader, cert, ca, leafPub, caKey)
			if e != nil {
				t.Fatal(e)
			}
			f.Members[i].CertificateDER = der
			f.Members[i].CARootDER = copyBytes(caDER)
			f.Grants = append(f.Grants, grant{Role: "node-leaf", AuthorityScope: map[string]any{"class": "NODE", "scope": sc}, PublicKeyHex: hex.EncodeToString(leafPub), NotBefore: at.Add(-time.Hour), NotAfter: at.Add(time.Hour), Status: "ACTIVE"})
		}
		wantCode(t, checkPolicyBindings(f, measuredFor(f)), TrustUnknown)
	})
}

func TestReviewR3EveryOriginalOperationAndLease(t *testing.T) {
	p, h, st, c, packet := syntheticCryptoHistory(t)
	if len(h.Operations) != 2 {
		t.Fatalf("control requires actual two-operation fixture, got %d", len(h.Operations))
	}
	if e := checkOriginalHistory(p, h); e != nil {
		t.Fatal(e)
	}
	mutants := []struct {
		name   string
		change func(*historyData)
	}{
		{"three-way-current-original-kept", func(h *historyData) {
			old := h.Operations[h.Query.OriginalOperationID]
			old.OperationID = "substitute-current"
			h.Operations[old.OperationID] = old
			h.Query.OriginalOperationID = old.OperationID
			h.SemanticInputs.(map[string]any)["facts"].(map[string]any)["migrationOperationId"] = old.OperationID
		}},
		{"extra-operation-reuses-original-HELD", func(h *historyData) {
			old := h.Operations[h.Query.OriginalOperationID]
			old.OperationID = "extra-unrelated"
			h.Operations[old.OperationID] = old
		}},
		{"extra-key-ID-mismatch", func(h *historyData) {
			old := h.Operations[h.Query.OriginalOperationID]
			old.LeaseEnvelopeSHA256 = hx("a", 64)
			h.Operations["different-key"] = old
		}},
		{"extra-missing-migration", func(h *historyData) {
			old := h.Operations[h.Query.OriginalOperationID]
			old.OperationID = "extra"
			old.LeaseEnvelopeSHA256 = hx("a", 64)
			old.MigrationID = ""
			h.Operations[old.OperationID] = old
		}},
		{"extra-zero-fence", func(h *historyData) {
			old := h.Operations[h.Query.OriginalOperationID]
			old.OperationID = "extra"
			old.LeaseEnvelopeSHA256 = hx("a", 64)
			old.FenceEpoch = 0
			h.Operations[old.OperationID] = old
		}},
		{"extra-bad-hash", func(h *historyData) {
			old := h.Operations[h.Query.OriginalOperationID]
			old.OperationID = "extra"
			old.LeaseEnvelopeSHA256 = "not-a-hash"
			h.Operations[old.OperationID] = old
		}},
		{"extra-non-UTC", func(h *historyData) {
			old := h.Operations[h.Query.OriginalOperationID]
			old.OperationID = "extra"
			old.LeaseEnvelopeSHA256 = hx("a", 64)
			old.AcquiredAt = old.AcquiredAt.In(time.FixedZone("not-UTC", 0))
			h.Operations[old.OperationID] = old
		}},
		{"extra-reversed-interval", func(h *historyData) {
			old := h.Operations[h.Query.OriginalOperationID]
			old.OperationID = "extra"
			old.LeaseEnvelopeSHA256 = hx("a", 64)
			old.ExpiresAt = old.AcquiredAt
			h.Operations[old.OperationID] = old
		}},
	}
	for _, m := range mutants {
		t.Run(m.name, func(t *testing.T) {
			f, e := freezeHistory(h)
			if e != nil {
				t.Fatal(e)
			}
			m.change(&f)
			wantCode(t, checkOriginalHistory(p, f), OriginalOperationMismatch)
			_, e = evaluateBoundHistory(p, f, st, c, packet)
			wantCode(t, e, OriginalOperationMismatch)
			// Private ALREADY-BOUND SYNTHETIC DTOs bypass only the still-missing
			// external auth, so exercise public-service first-failed precedence.
			s := NewService()
			pf, e := freezePolicy(p)
			if e != nil {
				t.Fatal(e)
			}
			pd, e := policyDigest(pf)
			if e != nil {
				t.Fatal(e)
			}
			hd, e := historyDigest(f)
			if e != nil {
				t.Fatal(e)
			}
			ip := &InstalledPolicy{binding: &policyBinding{owner: s, version: pf.Version, digest: pd, data: pf}}
			ih := &History{binding: &historyBinding{owner: s, policyDigest: pd, digest: hd, data: f}}
			_, e = s.ValidateHistory(packet, ip, ih)
			wantCode(t, e, OriginalOperationMismatch)
		})
	}
}
