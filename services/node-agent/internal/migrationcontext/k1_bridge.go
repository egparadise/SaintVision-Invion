package migrationcontext

// Sole new production K1 import and construction/call site. No current path.
import (
	k1 "github.com/egparadise/SaintVision-Invion/services/node-agent/migrationverify"
	"time"
)

func canonicalValue(v any) ([]byte, error) {
	f, e := cloneJSON(v)
	if e != nil {
		return nil, e
	}
	return k1.CanonicalJSON(f)
}
func cohortScopeHash(p policyData) (string, error) {
	members := make([]any, len(p.Members))
	for i, m := range p.Members {
		members[i] = m.Scope
	}
	b, e := canonicalValue(map[string]any{"class": "COHORT", "cohortId": p.CohortID, "members": members})
	if e != nil {
		return "", e
	}
	return hashBytes(b), nil
}

func verifyK1History(p policyData, h historyData, st statusData, packet UntrustedPacket, at time.Time) (HistoryReport, error) {
	installed := k1.InstalledTrust{RegistrySHA256: p.RegistrySHA256, Verifier: k1.VerifierPublication{ID: p.Verifier.ID, SourceSHA: p.Verifier.SourceSHA, ArtifactSHA256: p.Verifier.ArtifactSHA256, ReviewSHA: p.Verifier.ReviewSHA, CIRunIDs: append([]string(nil), p.Verifier.CIRunIDs...)}, ContractPins: map[string]k1.ContractPin{}, CohortID: p.CohortID, GraphBytes: copyBytes(p.GraphBytes), GraphSHA256: p.GraphSHA256, NodeKinds: copyMap(p.NodeKinds)}
	for id, v := range p.ContractPins {
		installed.ContractPins[id] = k1.ContractPin{ContractSHA256: v.ContractSHA256, SchemaSHA256: v.SchemaSHA256, Codec: v.Codec, RequiredVerifier: v.RequiredVerifier}
	}
	for _, v := range p.Grants {
		sc, e := cloneJSON(v.AuthorityScope)
		if e != nil {
			return HistoryReport{}, refuse(K1Refused)
		}
		installed.Grants = append(installed.Grants, k1.KeyGrant{Role: v.Role, AuthorityScope: sc, PublicKeyHex: v.PublicKeyHex, NotBefore: v.NotBefore, NotAfter: v.NotAfter, Status: v.Status})
	}
	for _, v := range p.Members {
		sc, e := cloneJSON(v.Scope)
		if e != nil {
			return HistoryReport{}, refuse(K1Refused)
		}
		installed.Members = append(installed.Members, k1.MemberIdentity{Slot: v.Slot, Scope: sc, CertificateDER: copyBytes(v.CertificateDER), CARootDER: copyBytes(v.CARootDER)})
	}
	semantic, e := cloneJSON(h.SemanticInputs)
	if e != nil {
		return HistoryReport{}, refuse(K1Refused)
	}
	ctx := k1.TrustedContext{Now: at, SemanticInputs: semantic, MigrationOperationID: h.Query.OriginalOperationID, History: k1.HistoricalContext{Operations: map[string]k1.OperationBinding{}, Challenges: map[string]k1.NativeChallenge{}}, Publications: map[string]k1.PublicationStatus{}, Certificates: map[string]k1.CertificateStatus{}}
	for id, v := range h.Operations {
		ctx.History.Operations[id] = k1.OperationBinding{MigrationID: v.MigrationID, OperationID: v.OperationID, LeaseEnvelopeSHA256: v.LeaseEnvelopeSHA256, FenceEpoch: v.FenceEpoch, AcquiredAt: v.AcquiredAt, ExpiresAt: v.ExpiresAt}
	}
	for id, v := range h.Challenges {
		ctx.History.Challenges[id] = k1.NativeChallenge{Nonce: v.Nonce, MigrationID: v.MigrationID, OperationID: v.OperationID, ScopeSHA256: v.ScopeSHA256, FenceEpoch: v.FenceEpoch, IssuedAt: v.IssuedAt, ExpiresAt: v.ExpiresAt}
	}
	for id, v := range st.Publications {
		ctx.Publications[id] = k1.PublicationStatus{Status: v.Status, SubjectSHA256: v.SubjectSHA256, PublishedAt: v.PublishedAt, CheckedAt: v.CheckedAt, ExpiresAt: v.ExpiresAt}
	}
	for id, v := range st.Certificates {
		ctx.Certificates[id] = k1.CertificateStatus{Status: v.Status, CheckedAt: v.CheckedAt, ExpiresAt: v.ExpiresAt}
	}
	v, e := k1.NewVerifier(installed, ctx)
	if e != nil {
		return HistoryReport{}, refuse(K1Refused)
	}
	r, e := v.Verify(k1.Packet{Records: packet.Records, Referents: packet.Referents})
	if e != nil {
		return HistoryReport{}, refuse(K1Refused)
	}
	return HistoryReport{Classification: r.Classification, Records: r.Records, ProofReferences: r.ProofReferences, RealSignatures: r.RealSignatures, Digests: copyMap(r.Digests)}, nil
}
