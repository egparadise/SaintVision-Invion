package migrationverify

import (
	"crypto/ed25519"
	"encoding/json"
	"errors"
	"fmt"
	"time"
)

// InstalledTrust is a TRUSTED APPLICATION INPUT, loaded independently of any
// plan or bundle. K1 never loads it from a packet, installs it, or discovers a
// default. K2 must bind these values to actual reviewed installation evidence.
// There is no executable callback, test-policy flag or bundle verifier selector.
type InstalledTrust struct {
	RegistrySHA256 string
	Verifier       VerifierPublication
	ContractPins   map[string]ContractPin
	Grants         []KeyGrant
	CohortID       string
	Members        []MemberIdentity // Exact ordered complete scope vector.
	GraphBytes     []byte
	GraphSHA256    string
	NodeKinds      map[string]string
}
type VerifierPublication struct {
	ID, SourceSHA, ArtifactSHA256, ReviewSHA string
	CIRunIDs                                 []string
}
type ContractPin struct{ ContractSHA256, SchemaSHA256, Codec, RequiredVerifier string }
type KeyGrant struct {
	Role                string
	AuthorityScope      any
	PublicKeyHex        string // Raw Ed25519 PUBLIC bytes, never a private key.
	NotBefore, NotAfter time.Time
	Status              string // Exact current external registration state: ACTIVE only.
}
type MemberIdentity struct {
	Slot           string
	Scope          any
	CertificateDER []byte
	CARootDER      []byte
}

// TrustedContext is another independent application input, not packet metadata.
// Facts/operations/challenges/publication decisions must come from K2's actual
// trusted producers. No bool can turn supplied bundle values into authority.
// K1 copies all mutable values before use; it neither reads nor overrides a
// physical clock. Tests supply explicitly synthetic times in test-only code.
type TrustedContext struct {
	Now                  time.Time
	SemanticInputs       any
	Operations           map[string]OperationBinding
	MigrationOperationID string
	Challenges           map[string]NativeChallenge   // operationId + NUL + C2(scope) hash.
	Publications         map[string]PublicationStatus // Exact referent raw SHA256.
	Certificates         map[string]CertificateStatus // Exact authenticated leaf DER hash.
	Current              *CurrentProjectionContext
}
type OperationBinding struct {
	MigrationID, OperationID, LeaseEnvelopeSHA256 string
	FenceEpoch                                    int64
	AcquiredAt, ExpiresAt                         time.Time
}
type NativeChallenge struct {
	Nonce, MigrationID, OperationID, ScopeSHA256 string
	FenceEpoch                                   int64
	IssuedAt, ExpiresAt                          time.Time
}
type PublicationStatus struct {
	Status, SubjectSHA256             string
	PublishedAt, CheckedAt, ExpiresAt time.Time
}
type CertificateStatus struct {
	Status               string
	CheckedAt, ExpiresAt time.Time
}
type CurrentProjectionContext struct {
	SetID, MigrationID, OperationID, PlanEnvelopeSHA256, LeaseEnvelopeSHA256 string
	FenceEpoch, Sequence                                                     int64
	InventoryHead                                                            any
	InventoryReadbackSHA256                                                  string
	MemberProjectionSHA256                                                   []string
}

type verifierKey struct {
	public        ed25519.PublicKey
	before, after time.Time
}
type Verifier struct {
	trust     InstalledTrust
	ctx       TrustedContext
	schemas   *Schemas
	contracts *contracts
	graph     *graph
	keys      map[string]verifierKey
}

func jsonCopy(v any) (any, error) {
	b, e := json.Marshal(v)
	if e != nil {
		return nil, e
	}
	return ParseJSON(b)
}
func goodHash(s string, n int) bool {
	_, e := exactHex(s, n)
	if e != nil {
		return false
	}
	for _, c := range s {
		if c != '0' {
			return true
		}
	}
	return false
}

func NewVerifier(installed InstalledTrust, context TrustedContext) (*Verifier, error) {
	if !goodHash(installed.RegistrySHA256, 32) || installed.Verifier.ID != "saintvision-migrationverify-k1:1" || !goodHash(installed.Verifier.SourceSHA, 20) || !goodHash(installed.Verifier.ArtifactSHA256, 32) || !goodHash(installed.Verifier.ReviewSHA, 20) || len(installed.Verifier.CIRunIDs) == 0 {
		return nil, errors.New("missing externally registered verifier provenance")
	}
	if installed.CohortID == "" || len(installed.Members) != 2 || installed.Members[0].Slot != "PC2" || installed.Members[1].Slot != "PC4" {
		return nil, errors.New("missing ordered external cohort")
	}
	if context.Now.IsZero() || context.Now.Location() != time.UTC {
		return nil, errors.New("missing trusted UTC observation time")
	}
	// Copy through typed encoding to sever every caller-owned slice/map, without
	// accepting JSON from the untrusted packet as an installed policy.
	b, e := json.Marshal(installed)
	if e != nil {
		return nil, e
	}
	var t InstalledTrust
	if e = json.Unmarshal(b, &t); e != nil {
		return nil, e
	}
	for i := range t.Members {
		t.Members[i].Scope, e = jsonCopy(installed.Members[i].Scope)
		if e != nil {
			return nil, e
		}
		if _, e = scopeIdentity(t.Members[i].Scope); e != nil {
			return nil, e
		}
	}
	if equal(t.Members[0].Scope, t.Members[1].Scope) {
		return nil, errors.New("duplicate external Node scope")
	}
	b, e = json.Marshal(context)
	if e != nil {
		return nil, e
	}
	var ctx TrustedContext
	if e = json.Unmarshal(b, &ctx); e != nil {
		return nil, e
	}
	ctx.SemanticInputs, e = jsonCopy(context.SemanticInputs)
	if e != nil {
		return nil, e
	}
	if ctx.Current != nil {
		ctx.Current.InventoryHead, e = jsonCopy(context.Current.InventoryHead)
		if e != nil {
			return nil, e
		}
	}
	s, e := LoadSchemas()
	if e != nil {
		return nil, e
	}
	cs, e := loadContracts()
	if e != nil {
		return nil, e
	}
	if len(t.ContractPins) != len(cs.byID) {
		return nil, errors.New("missing or unknown installed contract pins")
	}
	for id, c := range cs.byID {
		p, ok := t.ContractPins[id]
		if !ok || p.ContractSHA256 != c.hash || p.SchemaSHA256 != c.schemaHash || p.Codec != c.codec || p.RequiredVerifier != c.verifier {
			return nil, fmt.Errorf("unregistered proof contract %s", id)
		}
	}
	if !goodHash(t.GraphSHA256, 32) || shaHex(t.GraphBytes) != t.GraphSHA256 {
		return nil, errors.New("missing external graph pin")
	}
	g, e := compileGraph(t.GraphBytes, t.NodeKinds)
	if e != nil {
		return nil, e
	}
	v := &Verifier{trust: t, ctx: ctx, schemas: s, contracts: cs, graph: g, keys: map[string]verifierKey{}}
	for i, k := range t.Grants {
		if k.Status != "ACTIVE" || k.NotBefore.IsZero() || !k.NotAfter.After(k.NotBefore) {
			return nil, errors.New("inactive or invalid external key grant")
		}
		k.AuthorityScope, e = jsonCopy(installed.Grants[i].AuthorityScope)
		if e != nil {
			return nil, e
		}
		pub, e := exactHex(k.PublicKeyHex, 32)
		if e != nil {
			return nil, e
		}
		if e = decodePrimePoint(pub); e != nil {
			return nil, e
		}
		spki, e := publicSPKI(pub)
		if e != nil {
			return nil, e
		}
		sc, e := canonicalHash(k.AuthorityScope)
		if e != nil {
			return nil, e
		}
		id := k.Role + "\x00" + sc + "\x00" + spki
		if _, ok := v.keys[id]; ok {
			return nil, errors.New("duplicate external role/scope key grant")
		}
		v.keys[id] = verifierKey{pub, k.NotBefore, k.NotAfter}
	}
	if len(v.keys) == 0 {
		return nil, errors.New("no external key grants")
	}
	return v, nil
}

func (v *Verifier) key(role string, scope any, spki string) (ed25519.PublicKey, error) {
	return v.keyAt(role, scope, spki, v.ctx.Now)
}

func (v *Verifier) keyAt(role string, scope any, spki string, observed time.Time) (ed25519.PublicKey, error) {
	s, e := canonicalHash(scope)
	if e != nil {
		return nil, e
	}
	k, ok := v.keys[role+"\x00"+s+"\x00"+spki]
	if !ok || v.ctx.Now.Before(k.before) || !v.ctx.Now.Before(k.after) || observed.Before(k.before) || !observed.Before(k.after) {
		return nil, errors.New("key not authorized for exact current role/scope")
	}
	return k.public, nil
}

func scopeIdentity(v any) (map[string]any, error) {
	m, e := object(v)
	if e != nil || len(m) != 3 {
		return nil, errors.New("invalid Node identity scope")
	}
	for _, k := range []string{"tenantId", "nodeId", "recoveryEpoch"} {
		s, e := text(m[k])
		if e != nil || s == "" {
			return nil, errors.New("missing Node identity")
		}
	}
	return m, nil
}
func (v *Verifier) member(slot string) (MemberIdentity, error) {
	for _, m := range v.trust.Members {
		if m.Slot == slot {
			return m, nil
		}
	}
	return MemberIdentity{}, errors.New("unknown registered member")
}
func (v *Verifier) cohortAuthority() any {
	a := []any{}
	for _, m := range v.trust.Members {
		a = append(a, m.Scope)
	}
	return map[string]any{"class": "COHORT", "cohortId": v.trust.CohortID, "members": a}
}
func nodeAuthority(scope any) any { return map[string]any{"class": "NODE", "scope": scope} }
func componentAuthority(component string) any {
	return map[string]any{"class": "COMPONENT", "component": component}
}

func (v *Verifier) operation(id string) (OperationBinding, error) {
	o, ok := v.ctx.Operations[id]
	if !ok || o.OperationID != id || o.MigrationID == "" || o.FenceEpoch < 1 || !goodHash(o.LeaseEnvelopeSHA256, 32) || o.AcquiredAt.IsZero() || !o.ExpiresAt.After(o.AcquiredAt) {
		return o, errors.New("missing trusted operation/lease binding")
	}
	return o, nil
}
