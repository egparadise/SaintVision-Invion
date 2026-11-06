package migrationcontext

import "time"

// All fields are facts from a future independently authenticated clock/mechanism
// producer. This data structure is not its attestation protocol. No source,
// stdlib match or UTC/monotonic mapping is provisioned by this revision.
type clockEnvelope struct {
	L, U, T0                                                               time.Time
	PolicyVersion, CurrentVersion                                          string
	MechanismSourceSHA, StdlibSHA256, RunningClosureSHA256, MappingVersion string
	AcquisitionStart, EvaluationStart, Deadline, EvaluationEnd             int64
	MaxElapsedUncertainty                                                  time.Duration
}

func utc(t time.Time) bool { return !t.IsZero() && t.Location() == time.UTC }

// checkClock is pure envelope arithmetic over ALREADY BOUND synthetic facts.
// It never reads a physical clock or treats a format/field as authentication.
func checkClock(p policyData, h historyData, c clockEnvelope) error {
	if !validHash(c.MechanismSourceSHA, 20) || !validHash(c.StdlibSHA256, 32) || c.RunningClosureSHA256 != p.Provenance.LinkedClosureSHA256 || c.MappingVersion == "" {
		return refuse(ClockMechanismUnproven)
	}
	if c.PolicyVersion != p.Version || c.CurrentVersion != h.CurrentVersion {
		return refuse(StaleSnapshot)
	}
	zero := time.Time{}
	if !utc(c.L) || !utc(c.U) || !utc(c.T0) || c.U.Before(c.L) || c.T0.Before(c.L) || c.U.Before(c.T0) || (!c.L.After(zero) && !c.U.Before(zero)) || c.U.Sub(c.L) > time.Second || c.MaxElapsedUncertainty < 0 || c.MaxElapsedUncertainty > time.Second || c.U.Sub(c.L) > c.MaxElapsedUncertainty || c.AcquisitionStart < 0 || c.EvaluationStart < c.AcquisitionStart || c.Deadline < c.EvaluationStart || c.EvaluationEnd < c.EvaluationStart || c.EvaluationEnd > c.Deadline {
		return refuse(ClockIntervalInvalid)
	}
	return nil
}

func reportsEqual(a, b HistoryReport) bool {
	if a.Classification != b.Classification || a.Records != b.Records || a.ProofReferences != b.ProofReferences || a.RealSignatures != b.RealSignatures || len(a.Digests) != len(b.Digests) {
		return false
	}
	for k, v := range a.Digests {
		if w, ok := b.Digests[k]; !ok || w != v {
			return false
		}
	}
	return true
}

// evaluateBoundHistory is downstream pure logic. Its arguments are never
// constructed from public/unregistered providers in this slice. Test-only
// already-bound fixtures explicitly bypass the missing external authentication.
// One frozen input is evaluated at L,U,t0; no favorable endpoint or retry.
func evaluateBoundHistory(p policyData, h historyData, st statusData, c clockEnvelope, packet UntrustedPacket) (HistoryReport, error) {
	pf, e := freezePolicy(p)
	if e != nil {
		return HistoryReport{}, e
	}
	hf, e := freezeHistory(h)
	if e != nil {
		return HistoryReport{}, e
	}
	pkt, e := freezePacket(packet)
	if e != nil {
		return HistoryReport{}, e
	}
	st.Publications = copyMap(st.Publications)
	st.Certificates = copyMap(st.Certificates)
	if e = checkOriginalHistory(pf, hf); e != nil {
		return HistoryReport{}, e
	}
	if e = checkClock(pf, hf, c); e != nil {
		return HistoryReport{}, e
	}
	var first HistoryReport
	for i, at := range []time.Time{c.L, c.U, c.T0} {
		if e = checkStatusBindings(pf, hf, st, at); e != nil {
			return HistoryReport{}, e
		}
		r, err := verifyK1History(pf, hf, st, pkt, at)
		if err != nil {
			return HistoryReport{}, err
		}
		if i == 0 {
			first = r
		} else if !reportsEqual(first, r) {
			return HistoryReport{}, refuse(ClockIntervalInvalid)
		}
	}
	if e = checkClock(pf, hf, c); e != nil {
		return HistoryReport{}, e
	}
	return HistoryReport{Classification: first.Classification, Records: first.Records, ProofReferences: first.ProofReferences, RealSignatures: first.RealSignatures, Digests: copyMap(first.Digests)}, nil
}
