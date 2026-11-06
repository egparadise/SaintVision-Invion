package migrationcontext

import (
	"bytes"
	"crypto/ed25519"
	"crypto/sha256"
	"crypto/x509"
	"encoding/hex"
	"encoding/json"
	"strings"
	"time"
	"unicode/utf8"
)

// InstalledPolicy is opaque and service-bound. No production constructor in this
// slice issues one. Its zero value and JSON-unmarshalled values are invalid.
type InstalledPolicy struct{ binding *policyBinding }
type policyBinding struct {
	owner           *Service
	version, digest string
	data            policyData
}

// Local mirrors keep K1 imports and construction confined to k1_bridge.go.
// Full underlying-type census gates changes to every reachable K1 input type.
type publication struct {
	ID, SourceSHA, ArtifactSHA256, ReviewSHA string
	CIRunIDs                                 []string
}
type contractPin struct{ ContractSHA256, SchemaSHA256, Codec, RequiredVerifier string }
type grant struct {
	Role                string
	AuthorityScope      any
	PublicKeyHex        string
	NotBefore, NotAfter time.Time
	Status              string
}
type member struct {
	Slot                      string
	Scope                     any
	CertificateDER, CARootDER []byte
}
type policyData struct {
	Selector, Version, RegistrySHA256 string
	Verifier                          publication
	ContractPins                      map[string]contractPin
	Grants                            []grant
	CohortID                          string
	Members                           []member
	GraphBytes                        []byte
	GraphSHA256                       string
	NodeKinds                         map[string]string
	Provenance                        provenance
}

// These are necessary binding facts, NOT authentication. Actual values are HOLD.
type provenance struct {
	ReviewTargetSHA, ReviewScope, ApprovedReviewScope, BinaryVCS, RuntimeLockSHA256 string
	CIHeadSHA, CIRef, CIWorkflow, CIRunID, CIAttempt, CIJobID, ArtifactDigest       string
	InstallationReceiptSHA256, RunningExecutableSHA256, LinkedClosureSHA256         string
}
type runningData struct{ ExecutableSHA256, InstallationReceiptSHA256, SourceSHA, RuntimeLockSHA256, LinkedClosureSHA256 string }

// LoadInstalledPolicy accepts an opaque registry locator, never a filesystem
// path. Registry availability/read/authentication is the actual executed gate.
// Authentication always refuses here; later pure consistency checks do not issue
// opaque inputs and are exercised only with private already-bound test fixtures.
func (s *Service) LoadInstalledPolicy(selector string) (*InstalledPolicy, error) {
	if s == nil || s.registry == nil || !validSelector(selector) {
		return nil, refuse(TrustUnknown)
	}
	r, err := s.registry.readRegistry(selector)
	if err != nil {
		return nil, refuse(TrustUnknown)
	}
	if err = authenticateRegistry(r); err != nil {
		return nil, err
	}
	// No opaque constructor follows an unregistered attestation.
	return nil, refuse(TrustUnknown)
}

func validSelector(s string) bool {
	if len(s) < 1 || len(s) > 128 {
		return false
	}
	for _, c := range s {
		if !(c >= 'a' && c <= 'z' || c >= 'A' && c <= 'Z' || c >= '0' && c <= '9' || c == '-' || c == '_') {
			return false
		}
	}
	return true
}
func hashBytes(b []byte) string { v := sha256.Sum256(b); return hex.EncodeToString(v[:]) }
func validHash(s string, n int) bool {
	b, e := hex.DecodeString(s)
	return e == nil && len(b) == n && s == strings.ToLower(s) && strings.Trim(s, "0") != ""
}

// cloneJSON accepts only a bounded JSON value algebra. It rejects custom
// marshalers, arbitrary structs/aliases and callbacks BEFORE encoding anything.
// It does not authenticate any value.
type jsonBudget struct{ nodes, bytes int }

func cloneJSON(v any) (any, error) {
	budget := jsonBudget{nodes: 100000, bytes: 32 << 20}
	return cloneValue(v, 0, &budget)
}
func cloneValue(v any, depth int, budget *jsonBudget) (any, error) {
	budget.nodes--
	if depth > 64 || budget.nodes < 0 || budget.bytes < 0 {
		return nil, refuse(HistoryUnknown)
	}
	switch x := v.(type) {
	case nil, bool:
		return x, nil
	case string:
		budget.bytes -= len(x)
		if !utf8.ValidString(x) || len(x) > 1<<20 || budget.bytes < 0 {
			return nil, refuse(HistoryUnknown)
		}
		return x, nil
	case json.Number:
		if len(x) > 128 || !json.Valid([]byte(x)) || len(x) == 0 || !(x[0] == '-' || x[0] >= '0' && x[0] <= '9') {
			return nil, refuse(HistoryUnknown)
		}
		return x, nil
	case map[string]any:
		if len(x) > budget.nodes {
			return nil, refuse(HistoryUnknown)
		}
		m := make(map[string]any, len(x))
		for k, v := range x {
			budget.bytes -= len(k)
			if !utf8.ValidString(k) || len(k) > 1024 || budget.bytes < 0 {
				return nil, refuse(HistoryUnknown)
			}
			c, e := cloneValue(v, depth+1, budget)
			if e != nil {
				return nil, e
			}
			m[k] = c
		}
		return m, nil
	case []any:
		if len(x) > budget.nodes {
			return nil, refuse(HistoryUnknown)
		}
		a := make([]any, len(x))
		for i, v := range x {
			c, e := cloneValue(v, depth+1, budget)
			if e != nil {
				return nil, e
			}
			a[i] = c
		}
		return a, nil
	default:
		return nil, refuse(HistoryUnknown)
	}
}
func copyMap[V any](m map[string]V) map[string]V {
	o := make(map[string]V, len(m))
	for k, v := range m {
		o[k] = v
	}
	return o
}
func copyBytes(b []byte) []byte { return append([]byte(nil), b...) }

func freezePolicy(in policyData) (policyData, error) {
	o := in
	o.Verifier.CIRunIDs = append([]string(nil), in.Verifier.CIRunIDs...)
	o.ContractPins = copyMap(in.ContractPins)
	o.NodeKinds = copyMap(in.NodeKinds)
	o.GraphBytes = copyBytes(in.GraphBytes)
	o.Grants = append([]grant(nil), in.Grants...)
	o.Members = append([]member(nil), in.Members...)
	for i := range o.Grants {
		c, e := cloneJSON(in.Grants[i].AuthorityScope)
		if e != nil {
			return policyData{}, refuse(TrustUnknown)
		}
		o.Grants[i].AuthorityScope = c
	}
	for i := range o.Members {
		c, e := cloneJSON(in.Members[i].Scope)
		if e != nil {
			return policyData{}, refuse(TrustUnknown)
		}
		o.Members[i].Scope = c
		o.Members[i].CertificateDER = copyBytes(in.Members[i].CertificateDER)
		o.Members[i].CARootDER = copyBytes(in.Members[i].CARootDER)
	}
	return o, nil
}
func policyDigest(p policyData) (string, error) {
	frozen, e := freezePolicy(p)
	if e != nil {
		return "", e
	}
	b, e := json.Marshal(frozen)
	if e != nil {
		return "", refuse(TrustUnknown)
	}
	return hashBytes(b), nil
}
func (s *Service) checkPolicy(p *InstalledPolicy) error {
	if s == nil || p == nil || p.binding == nil || p.binding.owner != s || p.binding.version == "" || p.binding.version != p.binding.data.Version {
		return refuse(TrustUnknown)
	}
	d, e := policyDigest(p.binding.data)
	if e != nil || d != p.binding.digest {
		return refuse(TrustUnknown)
	}
	return nil
}

// checkPolicyBindings is a pure consistency check, NOT a policy authenticator.
// Review/CI strings cannot authorize themselves; future registered producers
// must authenticate these exact identities and actual review scope separately.
func checkPolicyBindings(p policyData, measured runningData) error {
	v := p.Verifier
	pr := p.Provenance
	if !validSelector(p.Selector) || p.Version == "" || !validHash(p.RegistrySHA256, 32) || hashBytes(p.GraphBytes) != p.GraphSHA256 || !validHash(p.GraphSHA256, 32) || len(p.ContractPins) == 0 || len(p.Grants) == 0 || len(p.NodeKinds) == 0 || p.CohortID == "" {
		return refuse(TrustUnknown)
	}
	if v.ID != "saintvision-migrationverify-k1:1" || !validHash(v.SourceSHA, 20) || !validHash(v.ArtifactSHA256, 32) || !validHash(v.ReviewSHA, 20) || len(v.CIRunIDs) == 0 || pr.CIRunID == "" || pr.CIAttempt == "" || pr.CIJobID == "" || pr.CIRef == "" || pr.CIWorkflow == "" || !validHash(pr.ArtifactDigest, 32) || pr.CIHeadSHA != v.SourceSHA || pr.BinaryVCS != v.SourceSHA || pr.ReviewTargetSHA != v.SourceSHA || pr.ReviewScope == "" || pr.ReviewScope != pr.ApprovedReviewScope {
		return refuse(TrustUnknown)
	}
	runFound := false
	for _, id := range v.CIRunIDs {
		if id == pr.CIRunID {
			runFound = true
		}
	}
	if !runFound {
		return refuse(TrustUnknown)
	}
	if len(p.Members) != 2 || p.Members[0].Slot != "PC2" || p.Members[1].Slot != "PC4" {
		return refuse(TrustUnknown)
	}
	for _, m := range p.Members {
		sc, ok := m.Scope.(map[string]any)
		if !ok || len(sc) != 3 || len(m.CertificateDER) == 0 || len(m.CARootDER) == 0 {
			return refuse(TrustUnknown)
		}
		for _, k := range []string{"tenantId", "nodeId", "recoveryEpoch"} {
			v, ok := sc[k].(string)
			if !ok || v == "" {
				return refuse(TrustUnknown)
			}
		}
	}
	for _, g := range p.Grants {
		if g.Role == "" || g.Status != "ACTIVE" || !validHash(g.PublicKeyHex, 32) || g.AuthorityScope == nil || !utc(g.NotBefore) || !utc(g.NotAfter) || !g.NotBefore.Before(g.NotAfter) {
			return refuse(TrustUnknown)
		}
	}
	if e := checkMemberBindings(p); e != nil {
		return e
	}
	if !validHash(pr.RuntimeLockSHA256, 32) || !validHash(pr.InstallationReceiptSHA256, 32) || !validHash(pr.LinkedClosureSHA256, 32) || !validHash(measured.ExecutableSHA256, 32) || !validHash(measured.InstallationReceiptSHA256, 32) {
		return refuse(InstallationUnknown)
	}
	if measured.ExecutableSHA256 != v.ArtifactSHA256 || pr.RunningExecutableSHA256 != measured.ExecutableSHA256 || measured.SourceSHA != v.SourceSHA || measured.InstallationReceiptSHA256 != pr.InstallationReceiptSHA256 || measured.RuntimeLockSHA256 != pr.RuntimeLockSHA256 || measured.LinkedClosureSHA256 != pr.LinkedClosureSHA256 {
		return refuse(RunningIdentityMismatch)
	}
	return nil
}

// Exact DER/SPKI/URI and role/C2 joins are necessary even for an already-bound
// registry. None authenticates the registry's independent authorization. K1
// additionally checks each consuming-time grant, chain, native signature and
// current nonrevocation when verifying the original packet.
func checkMemberBindings(p policyData) error {
	seen := map[string]bool{}
	for _, g := range p.Grants {
		b, e := canonicalValue(g.AuthorityScope)
		if e != nil {
			return refuse(TrustUnknown)
		}
		id := g.Role + "\x00" + hashBytes(b) + "\x00" + g.PublicKeyHex
		if seen[id] {
			return refuse(TrustUnknown)
		}
		seen[id] = true
	}
	for _, m := range p.Members {
		cert, e := x509.ParseCertificate(m.CertificateDER)
		if e != nil {
			return refuse(TrustUnknown)
		}
		ca, e := x509.ParseCertificate(m.CARootDER)
		if e != nil {
			return refuse(TrustUnknown)
		}
		if cert.IsCA || !ca.IsCA || !bytes.Equal(cert.Raw, m.CertificateDER) || !bytes.Equal(ca.Raw, m.CARootDER) || cert.CheckSignatureFrom(ca) != nil || cert.KeyUsage&x509.KeyUsageDigitalSignature == 0 {
			return refuse(TrustUnknown)
		}
		serverAuth := false
		for _, u := range cert.ExtKeyUsage {
			if u == x509.ExtKeyUsageServerAuth {
				serverAuth = true
			}
		}
		if !serverAuth {
			return refuse(TrustUnknown)
		}
		sc, ok := m.Scope.(map[string]any)
		if !ok {
			return refuse(TrustUnknown)
		}
		uri := "spiffe://saintvision.ai/tenant/" + sc["tenantId"].(string) + "/node/" + sc["nodeId"].(string) + "/epoch/" + sc["recoveryEpoch"].(string)
		pub, ok := cert.PublicKey.(ed25519.PublicKey)
		if !ok || len(cert.URIs) != 1 || cert.URIs[0].String() != uri {
			return refuse(TrustUnknown)
		}
		want, e := canonicalValue(map[string]any{"class": "NODE", "scope": sc})
		if e != nil {
			return refuse(TrustUnknown)
		}
		found := false
		for _, g := range p.Grants {
			got, e := canonicalValue(g.AuthorityScope)
			if e != nil {
				return refuse(TrustUnknown)
			}
			if g.Role == "node-leaf" && g.PublicKeyHex == hex.EncodeToString(pub) && bytes.Equal(got, want) {
				found = true
			}
		}
		if !found {
			return refuse(TrustUnknown)
		}
	}
	return nil
}
