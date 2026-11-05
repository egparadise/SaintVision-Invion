package migrationverify

import (
	"bytes"
	"crypto/ed25519"
	"crypto/x509"
	"encoding/json"
	"errors"
	"time"
)

type nativeOriginal struct {
	body        map[string]any
	subject     any
	certificate *x509.Certificate
	spki        string
	observed    time.Time
}

// NativeHistory authenticates immutable ORIGINAL native bytes only. It contains
// no validUntil/current-operation/lease/nonce authorization or admission result.
// It cannot substitute for a bound embedded proof or current derivation.
type NativeHistory struct {
	Classification, ExactReferentSHA256, ObservedAt string
	Subject                                         any
}

func (v *Verifier) AuthenticateNativeHistory(raw []byte, registeredSlot string) (NativeHistory, error) {
	x, e := v.authenticateNativeOriginal(raw, registeredSlot, time.Time{})
	if e != nil {
		return NativeHistory{}, e
	}
	return NativeHistory{"AUTHENTICATED_ORIGINAL_NATIVE_HISTORY_NOT_FRESH_PROOF", shaHex(raw), x.observed.Format("2006-01-02T15:04:05Z"), copyJSON(x.subject)}, nil
}

func (v *Verifier) authenticateNativeOriginal(raw []byte, registeredSlot string, chainTime time.Time) (nativeOriginal, error) {
	var out nativeOriginal
	if v == nil || v.contracts == nil {
		return out, errors.New("missing installed native verifier")
	}
	c := v.contracts.byID["saintvision-proof-node-floor-v2:1"]
	if c == nil || c.codec != "native-m2-v2" {
		return out, errors.New("native codec unregistered")
	}
	value, e := ParseJSON(raw)
	if e != nil {
		return out, e
	}
	if e = protocolStrings(value); e != nil {
		return out, e
	}
	if e = c.schema.Validate(value); e != nil {
		return out, e
	}
	m, _ := object(value)
	sec, e := m["observedAt"].(json.Number).Int64()
	if e != nil {
		return out, e
	}
	observed := time.Unix(sec, 0).UTC()
	if observed.Year() < 1 || observed.Year() > 9999 {
		return out, errors.New("native observation outside canonical UTC calendar")
	}
	member, e := v.member(registeredSlot)
	if e != nil {
		return out, e
	}
	scope, e := scopeIdentity(member.Scope)
	if e != nil {
		return out, e
	}
	if len(member.CertificateDER) == 0 || len(member.CARootDER) == 0 {
		return out, errors.New("native unchanged certificate/CA absent")
	}
	cert, e := x509.ParseCertificate(member.CertificateDER)
	if e != nil {
		return out, e
	}
	ca, e := x509.ParseCertificate(member.CARootDER)
	if e != nil {
		return out, e
	}
	if cert.IsCA || !ca.IsCA || !bytes.Equal(cert.Raw, member.CertificateDER) || !bytes.Equal(ca.Raw, member.CARootDER) {
		return out, errors.New("native exact DER/CA mismatch")
	}
	serverAuth := false
	for _, usage := range cert.ExtKeyUsage {
		if usage == x509.ExtKeyUsageServerAuth {
			serverAuth = true
		}
	}
	if !serverAuth || cert.KeyUsage&x509.KeyUsageDigitalSignature == 0 {
		return out, errors.New("native leaf requires explicit ServerAuth and DigitalSignature")
	}
	derHash := shaHex(cert.Raw)
	status, ok := v.ctx.Certificates[derHash]
	now := v.ctx.Now
	if !ok || status.Status != "UNREVOKED" || status.CheckedAt.After(now) || now.Sub(status.CheckedAt) > 120*time.Second || !now.Before(status.ExpiresAt) {
		return out, errors.New("native current certificate nonrevocation state unavailable")
	}
	if chainTime.IsZero() {
		chainTime = observed
	}
	roots := x509.NewCertPool()
	roots.AddCert(ca)
	if _, e = cert.Verify(x509.VerifyOptions{Roots: roots, CurrentTime: chainTime, KeyUsages: []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth}}); e != nil {
		return out, e
	}
	identity := "spiffe://saintvision.ai/tenant/" + scope["tenantId"].(string) + "/node/" + scope["nodeId"].(string) + "/epoch/" + scope["recoveryEpoch"].(string)
	if len(cert.URIs) != 1 || cert.URIs[0].String() != identity {
		return out, errors.New("native certificate Node identity mismatch")
	}
	key, ok := cert.PublicKey.(ed25519.PublicKey)
	if !ok {
		return out, errors.New("native certificate is not Ed25519")
	}
	spki, e := publicSPKI(key)
	if e != nil {
		return out, e
	}
	if _, e = v.keyAt(c.role, nodeAuthority(scope), spki, observed); e != nil {
		return out, e
	}
	if _, e = v.keyAt(c.role, nodeAuthority(scope), spki, chainTime); e != nil {
		return out, e
	}
	for _, k := range []string{"tenantId", "nodeId", "recoveryEpoch"} {
		if m[k] != scope[k] {
			return out, errors.New("native signed identity mismatch")
		}
	}
	if m["certificateDER_SHA256"] != derHash {
		return out, errors.New("native signed DER hash mismatch")
	}
	if observed.Before(cert.NotBefore) || !observed.Before(cert.NotAfter) {
		return out, errors.New("native observation outside original certificate validity")
	}
	body := copyJSON(m).(map[string]any)
	delete(body, "nodeSignature")
	b, e := CanonicalJSON(body)
	if e != nil {
		return out, e
	}
	sig, e := exactHex(m["nodeSignature"].(string), 64)
	if e != nil {
		return out, e
	}
	if e = verifyEd25519(key, append([]byte(c.domain+"\x00"), b...), sig); e != nil {
		return out, e
	}
	subject := map[string]any{"kind": "node-floor-v2", "scope": scope, "certificateDERSHA256": derHash}
	for _, k := range []string{"nonce", "peerPolicyVersion", "peerPolicySHA256", "floorSHA256", "journalIdentitySHA256", "journalUID", "servingPID", "servingExecutableSHA256", "servingProcessSHA256"} {
		subject[k] = m[k]
	}
	if e = c.subjectSchema.Validate(subject); e != nil {
		return out, e
	}
	return nativeOriginal{m, subject, cert, spki, observed}, nil
}
