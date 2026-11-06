package migrationcontext

// These are closed internal composition contracts, not public injection hooks.
// The unexported methods/records prevent outside implementations. All results
// remain UNTRUSTED. No implementations or accepted attestation codecs exist.
type RegistryPort interface {
	readRegistry(string) (registryRecord, error)
}
type HistoryArchivePort interface {
	readHistory(historyRequest) (archiveRecord, error)
}
type StatusPort interface {
	readStatus(string) (statusRecord, error)
}
type ClockPort interface{ readClock() (clockRecord, error) }
type RunningCodeMeasurementPort interface{ readRunningCode() (runningRecord, error) }

type providerEvidence struct {
	purpose, format, version string
	raw                      []byte
}
type registryRecord struct {
	evidence providerEvidence
	data     policyData
}
type archiveRecord struct {
	evidence providerEvidence
	data     historyData
}
type statusRecord struct {
	evidence providerEvidence
	data     statusData
}
type clockRecord struct {
	evidence providerEvidence
	data     clockEnvelope
}
type runningRecord struct {
	evidence providerEvidence
	data     runningData
}

// Service has no exported fields, setters, options, provider callbacks or clock
// arguments. Future composition requires a separate reviewed grant and contract.
type Service struct {
	registry RegistryPort
	archive  HistoryArchivePort
	status   StatusPort
	clock    ClockPort
	running  RunningCodeMeasurementPort
}

func NewService() *Service { return &Service{} }

// There is intentionally no accepted purpose/format/key registry. Receiving any
// provider bytes must refuse, including well-formed hashes and self-signatures.
// These functions are NOT placeholder positive signature verifiers.
func authenticateRegistry(_ registryRecord) error        { return refuse(TrustUnknown) }
func authenticateArchive(_ archiveRecord) error          { return refuse(HistoryUnknown) }
func authenticateStatus(_ statusRecord) error            { return refuse(PublicationUnknown) }
func authenticateCertificateStatus(_ statusRecord) error { return refuse(CertificateUnknown) }
func authenticateClock(_ clockRecord) error              { return refuse(ClockUntrusted) }
func authenticateRunning(_ runningRecord) error          { return refuse(InstallationUnknown) }

// Independent acquisition gates let tests isolate later missing sources without
// pretending an all-null public call can report every first-failed-gate error.
// They issue no authenticated value.
func (s *Service) checkRunningSource() error {
	if s == nil || s.running == nil {
		return refuse(InstallationUnknown)
	}
	r, e := s.running.readRunningCode()
	if e != nil {
		return refuse(InstallationUnknown)
	}
	return authenticateRunning(r)
}
func (s *Service) checkPublicationSource(version string) error {
	if s == nil || s.status == nil {
		return refuse(PublicationUnknown)
	}
	r, e := s.status.readStatus(version)
	if e != nil {
		return refuse(PublicationUnknown)
	}
	return authenticateStatus(r)
}
func (s *Service) checkCertificateSource(version string) error {
	if s == nil || s.status == nil {
		return refuse(CertificateUnknown)
	}
	r, e := s.status.readStatus(version)
	if e != nil {
		return refuse(CertificateUnknown)
	}
	return authenticateCertificateStatus(r)
}
func (s *Service) checkClockSource() error {
	if s == nil || s.clock == nil {
		return refuse(ClockUntrusted)
	}
	r, e := s.clock.readClock()
	if e != nil {
		return refuse(ClockUntrusted)
	}
	return authenticateClock(r)
}
