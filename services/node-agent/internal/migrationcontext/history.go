package migrationcontext

import (
	"encoding/json"
	"time"
)

// HistoryQuery is untrusted selection, not authority. Only an authenticated
// archive scoped by independently installed policy could satisfy it.
type HistoryQuery struct {
	CohortID, ScopeSHA256, Version, OriginalMigrationID, OriginalOperationID string
	OriginalLeaseSHA256, OriginalPlanBodySHA256, ArchiveSHA256               string
	FenceEpoch                                                               int64
}
type historyRequest struct {
	query         HistoryQuery
	policyVersion string
}
type operation struct {
	MigrationID, OperationID, LeaseEnvelopeSHA256 string
	FenceEpoch                                    int64
	AcquiredAt, ExpiresAt                         time.Time
}
type challenge struct {
	Nonce, MigrationID, OperationID, ScopeSHA256 string
	FenceEpoch                                   int64
	IssuedAt, ExpiresAt                          time.Time
}
type publicationStatus struct {
	Status, SubjectSHA256             string
	PublishedAt, CheckedAt, ExpiresAt time.Time
}
type certificateStatus struct {
	Status               string
	CheckedAt, ExpiresAt time.Time
}
type historyData struct {
	Query                         HistoryQuery
	PolicyVersion, CurrentVersion string
	SemanticInputs                any
	Operations                    map[string]operation
	Challenges                    map[string]challenge
	// Exact original archive byte objects, never a current readback substitute.
	OriginalLease, OriginalPlanBody, ArchiveBytes []byte
}
type statusData struct {
	PolicyVersion, CurrentVersion string
	Publications                  map[string]publicationStatus
	Certificates                  map[string]certificateStatus
}

// History is opaque, bound to one service, policy version and exact original
// archive read. It is not a lease, permit or source of live operation authority.
type History struct{ binding *historyBinding }
type historyBinding struct {
	owner                *Service
	policyDigest, digest string
	data                 historyData
}

// UntrustedPacket contains serialized history only. It cannot select a verifier,
// clock, installed key, provider, trust root, or a current operation.
type UntrustedPacket struct{ Records, Referents map[string][]byte }
type HistoryReport struct {
	Classification                           string
	Records, ProofReferences, RealSignatures int
	Digests                                  map[string]string
}

func (s *Service) ReadHistory(p *InstalledPolicy, query HistoryQuery) (*History, error) {
	if e := s.checkPolicy(p); e != nil {
		return nil, e
	}
	if query.CohortID != p.binding.data.CohortID || !validHash(query.ScopeSHA256, 32) || query.Version == "" || !validHash(query.ArchiveSHA256, 32) {
		return nil, refuse(HistoryUnknown)
	}
	scope, e := cohortScopeHash(p.binding.data)
	if e != nil || scope != query.ScopeSHA256 || query.OriginalMigrationID == "" || query.OriginalOperationID == "" || query.FenceEpoch < 1 || !validHash(query.OriginalLeaseSHA256, 32) || !validHash(query.OriginalPlanBodySHA256, 32) {
		return nil, refuse(OriginalOperationMismatch)
	}
	if s.archive == nil {
		return nil, refuse(HistoryUnknown)
	}
	r, e := s.archive.readHistory(historyRequest{query: query, policyVersion: p.binding.version})
	if e != nil {
		return nil, refuse(HistoryUnknown)
	}
	if e = authenticateArchive(r); e != nil {
		return nil, e
	}
	return nil, refuse(HistoryUnknown)
}

// ValidateHistory's deterministic first failed gate order is: opaque policy,
// opaque original history/selector, running-code availability/authentication,
// and mandatory unregistered-source refusal. Later publication/certificate/clock
// gates and frozen L/U/t0 evaluation are separate private downstream checks;
// public assembly through those gates is not implemented or granted in this slice.
func (s *Service) ValidateHistory(packet UntrustedPacket, p *InstalledPolicy, h *History) (HistoryReport, error) {
	if e := s.checkPolicy(p); e != nil {
		return HistoryReport{}, e
	}
	if e := s.checkHistory(p, h); e != nil {
		return HistoryReport{}, e
	}
	if e := s.checkRunningSource(); e != nil {
		return HistoryReport{}, e
	}
	// There is no fallthrough from an unregistered running-code purpose. In
	// particular, a returned matching executable digest does not authenticate it.
	return HistoryReport{}, refuse(InstallationUnknown)
}

func freezeHistory(in historyData) (historyData, error) {
	o := in
	c, e := cloneJSON(in.SemanticInputs)
	if e != nil {
		return historyData{}, e
	}
	o.SemanticInputs = c
	o.Operations = copyMap(in.Operations)
	o.Challenges = copyMap(in.Challenges)
	o.OriginalLease = copyBytes(in.OriginalLease)
	o.OriginalPlanBody = copyBytes(in.OriginalPlanBody)
	o.ArchiveBytes = copyBytes(in.ArchiveBytes)
	return o, nil
}
func historyDigest(h historyData) (string, error) {
	f, e := freezeHistory(h)
	if e != nil {
		return "", e
	}
	b, e := json.Marshal(f)
	if e != nil {
		return "", refuse(HistoryUnknown)
	}
	return hashBytes(b), nil
}
func (s *Service) checkHistory(p *InstalledPolicy, h *History) error {
	if e := s.checkPolicy(p); e != nil {
		return e
	}
	if s == nil || h == nil || h.binding == nil || h.binding.owner != s || h.binding.policyDigest != p.binding.digest || h.binding.data.PolicyVersion != p.binding.version {
		return refuse(HistoryUnknown)
	}
	d, e := historyDigest(h.binding.data)
	if e != nil || d != h.binding.digest {
		return refuse(HistoryUnknown)
	}
	return checkOriginalHistory(p.binding.data, h.binding.data)
}

// checkOriginalHistory never consults a current operation or repairs facts.
// Expired original HELD leases remain valid selectors for original events; K1
// authenticates their signed consuming times and original challenges separately.
func checkOriginalHistory(p policyData, h historyData) error {
	q := h.Query
	if q.CohortID != p.CohortID || q.Version == "" || h.PolicyVersion != p.Version || h.CurrentVersion == "" || !validHash(q.ScopeSHA256, 32) || hashBytes(h.ArchiveBytes) != q.ArchiveSHA256 {
		return refuse(HistoryUnknown)
	}
	inputs, ok := h.SemanticInputs.(map[string]any)
	if !ok {
		return refuse(OriginalOperationMismatch)
	}
	facts, ok := inputs["facts"].(map[string]any)
	if !ok || facts["migrationOperationId"] != q.OriginalOperationID {
		return refuse(OriginalOperationMismatch)
	}
	leases := map[string]bool{}
	for id, op := range h.Operations {
		if id == "" || id != op.OperationID || op.MigrationID == "" || op.FenceEpoch < 1 || !validHash(op.LeaseEnvelopeSHA256, 32) || !utc(op.AcquiredAt) || !utc(op.ExpiresAt) || !op.AcquiredAt.Before(op.ExpiresAt) || leases[op.LeaseEnvelopeSHA256] {
			return refuse(OriginalOperationMismatch)
		}
		leases[op.LeaseEnvelopeSHA256] = true
	}
	op, ok := h.Operations[q.OriginalOperationID]
	if !ok || q.OriginalOperationID == "" || q.OriginalMigrationID == "" || op.OperationID != q.OriginalOperationID || op.MigrationID != q.OriginalMigrationID || op.FenceEpoch != q.FenceEpoch || op.FenceEpoch < 1 || op.LeaseEnvelopeSHA256 != q.OriginalLeaseSHA256 || !validHash(q.OriginalLeaseSHA256, 32) || hashBytes(h.OriginalLease) != q.OriginalLeaseSHA256 || !utc(op.AcquiredAt) || !utc(op.ExpiresAt) || !op.AcquiredAt.Before(op.ExpiresAt) {
		return refuse(OriginalOperationMismatch)
	}
	plan, ok := inputs["plan"].(map[string]any)
	if !ok {
		return refuse(OriginalOperationMismatch)
	}
	b, e := canonicalValue(plan)
	if e != nil || !validHash(q.OriginalPlanBodySHA256, 32) || hashBytes(h.OriginalPlanBody) != q.OriginalPlanBodySHA256 || hashBytes(b) != q.OriginalPlanBodySHA256 {
		return refuse(OriginalOperationMismatch)
	}
	// Scope is derived from the complete ordered installed cohort, not a label
	// supplied with the archive. Original containing-epoch facts stay unchanged.
	scope, e := cohortScopeHash(p)
	if e != nil || scope != q.ScopeSHA256 {
		return refuse(OriginalOperationMismatch)
	}
	for key, ch := range h.Challenges {
		if ch.Nonce == "" || ch.OperationID == "" || ch.MigrationID == "" || !validHash(ch.ScopeSHA256, 32) || key != ch.OperationID+"\x00"+ch.ScopeSHA256 || ch.FenceEpoch < 1 || !utc(ch.IssuedAt) || !utc(ch.ExpiresAt) || !ch.IssuedAt.Before(ch.ExpiresAt) {
			return refuse(OriginalOperationMismatch)
		}
		op, ok := h.Operations[ch.OperationID]
		if !ok || op.MigrationID != ch.MigrationID || op.FenceEpoch != ch.FenceEpoch {
			return refuse(OriginalOperationMismatch)
		}
	}
	return nil
}

func freezePacket(p UntrustedPacket) (UntrustedPacket, error) {
	if len(p.Records) > 4096 || len(p.Referents) > 8192 {
		return UntrustedPacket{}, refuse(K1Refused)
	}
	o := UntrustedPacket{Records: make(map[string][]byte, len(p.Records)), Referents: make(map[string][]byte, len(p.Referents))}
	total := 0
	for i, m := range []map[string][]byte{p.Records, p.Referents} {
		for id, raw := range m {
			if len(raw) > (32<<20)-total {
				return UntrustedPacket{}, refuse(K1Refused)
			}
			total += len(raw)
			if i == 0 {
				o.Records[id] = copyBytes(raw)
			} else {
				o.Referents[id] = copyBytes(raw)
			}
		}
	}
	return o, nil
}

// checkStatusBindings assumes independently authenticated status facts ONLY in
// synthetic downstream tests in this revision. ACTIVE labels alone are not trust.
func checkStatusBindings(p policyData, h historyData, st statusData, at time.Time) error {
	if st.PolicyVersion != p.Version || st.CurrentVersion != h.CurrentVersion {
		return refuse(StaleSnapshot)
	}
	if len(st.Publications) == 0 {
		return refuse(PublicationUnknown)
	}
	for raw, x := range st.Publications {
		if !validHash(raw, 32) || !validHash(x.SubjectSHA256, 32) || x.Status != "ACCEPTED_UNREVOKED" || !utc(x.PublishedAt) || !utc(x.CheckedAt) || !utc(x.ExpiresAt) || at.Before(x.PublishedAt) || at.Before(x.CheckedAt) || at.Sub(x.CheckedAt) > 120*time.Second || !at.Before(x.ExpiresAt) {
			return refuse(PublicationUnknown)
		}
	}
	if len(st.Certificates) == 0 {
		return refuse(CertificateUnknown)
	}
	for raw, x := range st.Certificates {
		if !validHash(raw, 32) || x.Status != "UNREVOKED" || !utc(x.CheckedAt) || !utc(x.ExpiresAt) || at.Before(x.CheckedAt) || at.Sub(x.CheckedAt) > 120*time.Second || !at.Before(x.ExpiresAt) {
			return refuse(CertificateUnknown)
		}
	}
	return nil
}
