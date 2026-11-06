package migrationcontext

// Code is a closed refusal category, not an authorization or raw K1 diagnostic.
type Code string

const (
	TrustUnknown              Code = "TRUST_UNKNOWN_OR_PIN_MISMATCH"
	HistoryUnknown            Code = "HISTORICAL_BINDING_UNKNOWN"
	ClockUntrusted            Code = "CLOCK_UNTRUSTED"
	ClockMechanismUnproven    Code = "CLOCK_MECHANISM_UNPROVEN"
	ClockIntervalInvalid      Code = "CLOCK_INTERVAL_INVALID"
	PublicationUnknown        Code = "PUBLICATION_UNKNOWN_REVOKED_EXPIRED_OR_BACKDATED"
	CertificateUnknown        Code = "CERTIFICATE_STATUS_UNKNOWN_REVOKED_OR_EXPIRED"
	InstallationUnknown       Code = "INSTALLATION_OR_RUNTIME_CAPABILITY_UNKNOWN"
	RunningIdentityMismatch   Code = "RUNNING_VERIFIER_IDENTITY_MISMATCH"
	OriginalOperationMismatch Code = "ORIGINAL_PLAN_OPERATION_MISMATCH"
	StaleSnapshot             Code = "STALE_SNAPSHOT"
	K1Refused                 Code = "K1_VALIDATION_REFUSED"
)

// Refusal exposes only a closed code. It never embeds a provider or K1 error.
type Refusal struct{ code Code }

func (e *Refusal) Error() string { return string(e.code) }
func (e *Refusal) Code() Code    { return e.code }
func refuse(c Code) error        { return &Refusal{code: c} }
