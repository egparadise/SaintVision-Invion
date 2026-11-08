// Package recoverycandidate is a proposed non-serving custody protocol. It is
// deliberately not imported by inv-node, its M2 observer, or live admission.
package recoverycandidate

import (
	"bytes"
	"crypto/ed25519"
	"crypto/sha256"
	"crypto/x509"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"math"
	"net/url"
	"regexp"
	"strconv"
	"time"
)

const MaxBytes = 65536
const AuthorizationDomain = "saintvision/expired-policy/authorization/v1\x00"
const OperatorDomain = "saintvision/expired-policy/operator-custody/v1\x00"
const ProofDomain = "saintvision/expired-policy/nonserving-proof/v1\x00"
const AckDomain = "saintvision/expired-policy/checkpoint-request/v1\x00"
const CheckpointDomain = "saintvision/expired-policy/candidate-checkpoint/v1\x00"

type Refusal string

func (e Refusal) Error() string { return string(e) }

func refuse(code string) error { return Refusal(code) }

var hex64 = regexp.MustCompile(`^[0-9a-f]{64}$`)
var operationID = regexp.MustCompile(`^[0-9a-f]{32}$`)
var scopeID = regexp.MustCompile(`^[a-zA-Z0-9_-]{1,80}$`)

func Hash(raw []byte) string { h := sha256.Sum256(raw); return hex.EncodeToString(h[:]) }

// Canonical is a closed ASCII/integer subset. Both languages verify the exact
// payload bytes, duplicate keys and canonical encoding, never a lossy projection.
func Canonical(v any) ([]byte, error) {
	switch x := v.(type) {
	case map[string]any:
		for k, value := range x {
			if _, err := Canonical(k); err != nil { return nil, err }
			if _, err := Canonical(value); err != nil { return nil, err }
		}
	case []any:
		for _, value := range x { if _, err := Canonical(value); err != nil { return nil, err } }
	case string:
		for _, c := range x { if c < 32 || c > 126 || c == '<' || c == '>' || c == '&' { return nil, refuse("RECOVERY_WIRE_STRING") } }
	case json.Number:
		i, err := strconv.ParseInt(string(x), 10, 64)
		if err != nil || strconv.FormatInt(i, 10) != string(x) || i < -9007199254740991 || i > 9007199254740991 { return nil, refuse("RECOVERY_WIRE_NUMBER") }
	case int64:
		if x < -9007199254740991 || x > 9007199254740991 { return nil, refuse("RECOVERY_WIRE_NUMBER") }
	case int:
		if math.Abs(float64(x)) > 9007199254740991 { return nil, refuse("RECOVERY_WIRE_NUMBER") }
	case bool, nil:
	default:
		return nil, refuse("RECOVERY_WIRE_TYPE")
	}
	return json.Marshal(v)
}

func tokenValue(d *json.Decoder, depth int) (any, error) {
	if depth > 16 { return nil, refuse("RECOVERY_WIRE_DEPTH") }
	t, err := d.Token(); if err != nil { return nil, refuse("RECOVERY_WIRE_JSON") }
	if delim, ok := t.(json.Delim); ok {
		switch delim {
		case '{':
			m := map[string]any{}
			for d.More() {
				key, err := d.Token(); if err != nil { return nil, refuse("RECOVERY_WIRE_JSON") }
				k, ok := key.(string); if !ok { return nil, refuse("RECOVERY_WIRE_JSON") }
				if _, exists := m[k]; exists { return nil, refuse("RECOVERY_WIRE_DUPLICATE") }
				v, err := tokenValue(d, depth+1); if err != nil { return nil, err }; m[k] = v
			}
			if end, err := d.Token(); err != nil || end != json.Delim('}') { return nil, refuse("RECOVERY_WIRE_JSON") }; return m, nil
		case '[':
			a := []any{}
			for d.More() { if len(a) >= 128 { return nil, refuse("RECOVERY_WIRE_ARRAY") }; v, err := tokenValue(d, depth+1); if err != nil { return nil, err }; a = append(a, v) }
			if end, err := d.Token(); err != nil || end != json.Delim(']') { return nil, refuse("RECOVERY_WIRE_JSON") }; return a, nil
		}
		return nil, refuse("RECOVERY_WIRE_JSON")
	}
	return t, nil
}

func Parse(raw []byte) (map[string]any, error) {
	return parseObject(raw, true)
}

// Existing journal bytes are hashed exactly; their historical key order is not
// rewritten to the proposed wire canonicalization.
func ParseJournal(raw []byte) (map[string]any, error) { return parseObject(raw, false) }

func parseObject(raw []byte, requireCanonical bool) (map[string]any, error) {
	if len(raw) == 0 || len(raw) > MaxBytes { return nil, refuse("RECOVERY_WIRE_SIZE") }
	d := json.NewDecoder(bytes.NewReader(raw)); d.UseNumber()
	v, err := tokenValue(d, 0); if err != nil { return nil, err }
	if _, err := d.Token(); err != io.EOF { return nil, refuse("RECOVERY_WIRE_TRAILING") }
	m, ok := v.(map[string]any); if !ok { return nil, refuse("RECOVERY_WIRE_OBJECT") }
	c, err := Canonical(m); if err != nil { return nil, err }
	if requireCanonical && !bytes.Equal(c, raw) { return nil, refuse("RECOVERY_WIRE_NONCANONICAL") }
	return m, nil
}

func Closed(m map[string]any, names ...string) bool {
	if len(m) != len(names) { return false }
	for _, name := range names { if _, ok := m[name]; !ok { return false } }
	return true
}
func Text(m map[string]any, k string) string { s, _ := m[k].(string); return s }
func Number(m map[string]any, k string) int64 { n, ok := m[k].(json.Number); if !ok { return -1 }; i, err := strconv.ParseInt(string(n), 10, 64); if err != nil { return -1 }; return i }
func Object(m map[string]any, k string) map[string]any { v, _ := m[k].(map[string]any); return v }
func Array(m map[string]any, k string) []any { v, _ := m[k].([]any); return v }

func Verify(envelope map[string]any, domain string, pub ed25519.PublicKey) (map[string]any, []byte, error) {
	if !Closed(envelope, "payload", "signature") || len(pub) != ed25519.PublicKeySize { return nil, nil, refuse("RECOVERY_ENVELOPE") }
	raw, err := base64.StdEncoding.Strict().DecodeString(Text(envelope, "payload")); if err != nil || len(raw) > MaxBytes || base64.StdEncoding.EncodeToString(raw) != Text(envelope, "payload") { return nil, nil, refuse("RECOVERY_ENVELOPE") }
	sig, err := hex.DecodeString(Text(envelope, "signature")); if err != nil || len(sig) != ed25519.SignatureSize || !ed25519.Verify(pub, append([]byte(domain), raw...), sig) { return nil, nil, refuse("RECOVERY_SIGNATURE") }
	m, err := Parse(raw); return m, raw, err
}

func Sign(body map[string]any, domain string, key ed25519.PrivateKey) (map[string]any, error) {
	raw, err := Canonical(body); if err != nil { return nil, err }
	return map[string]any{"payload": base64.StdEncoding.EncodeToString(raw), "signature": hex.EncodeToString(ed25519.Sign(key, append([]byte(domain), raw...)))}, nil
}

// Exact single-CA candidate, separate from the unchanged generic two-chain path.
func ValidateLeaves(caRaw, cpRaw, nodeRaw []byte, tenant, epoch, nodeID, ip string, now int64) error {
	ca, err := x509.ParseCertificate(caRaw); if err != nil { return refuse("RECOVERY_CA") }
	if now >= ca.NotAfter.Unix() { return refuse("RECOVERY_TERMINAL_CA_EXPIRED") }
	if now < ca.NotBefore.Unix() || !bytes.Equal(ca.RawIssuer,ca.RawSubject) || !ca.MaxPathLenZero || len(ca.UnhandledCriticalExtensions) != 0 || !ca.IsCA || !ca.BasicConstraintsValid || ca.KeyUsage&x509.KeyUsageCertSign == 0 || ca.SignatureAlgorithm != x509.PureEd25519 || ca.CheckSignature(ca.SignatureAlgorithm, ca.RawTBSCertificate, ca.Signature) != nil { return refuse("RECOVERY_CA") }
	if _, ok := ca.PublicKey.(ed25519.PublicKey); !ok { return refuse("RECOVERY_ALGORITHM") }
	for index, raw := range [][]byte{cpRaw, nodeRaw} {
		cert, err := x509.ParseCertificate(raw); if err != nil { return refuse("RECOVERY_LEAF") }
		if now >= cert.NotAfter.Unix() { return refuse("RECOVERY_TERMINAL_LEAF_EXPIRED") }
		if now < cert.NotBefore.Unix() || cert.NotAfter.After(ca.NotAfter) || !bytes.Equal(cert.RawIssuer,ca.RawSubject) || len(cert.UnhandledCriticalExtensions) != 0 || len(cert.DNSNames) != 0 || len(cert.EmailAddresses) != 0 || len(cert.UnknownExtKeyUsage) != 0 || cert.IsCA || !cert.BasicConstraintsValid || cert.KeyUsage&x509.KeyUsageDigitalSignature == 0 || cert.CheckSignatureFrom(ca) != nil || cert.SignatureAlgorithm != x509.PureEd25519 { return refuse("RECOVERY_LEAF") }
		if _, ok := cert.PublicKey.(ed25519.PublicKey); !ok { return refuse("RECOVERY_ALGORITHM") }
		uri := "spiffe://saintvision.ai/tenant/"+tenant+"/control-plane/epoch/"+epoch; usage := x509.ExtKeyUsageClientAuth
		if index == 1 { uri = "spiffe://saintvision.ai/tenant/"+tenant+"/node/"+nodeID+"/epoch/"+epoch; usage = x509.ExtKeyUsageServerAuth }
		expected, _ := url.Parse(uri)
		if len(cert.URIs) != 1 || cert.URIs[0].String() != expected.String() || len(cert.ExtKeyUsage) != 1 || cert.ExtKeyUsage[0] != usage { return refuse("RECOVERY_SCOPE") }
		if index == 0 && len(cert.IPAddresses) != 0 { return refuse("RECOVERY_IP") }
		if index == 1 && (len(cert.IPAddresses) != 1 || cert.IPAddresses[0].String() != ip) { return refuse("RECOVERY_IP") }
		if cert.NotAfter.Unix()-now <= 660 { return refuse("RECOVERY_DEADLINE") }
	}
	return nil
}

func Fresh(body map[string]any, now int64) error {
	issued, deadline := Number(body, "issuedAt"), Number(body, "deadline")
	if issued > now+30 || now-issued > 120 || deadline <= now || deadline > issued+120 || deadline <= issued { return refuse("RECOVERY_CHALLENGE_EXPIRED") }
	return nil
}

func Clock() int64 { return time.Now().Unix() }

// Keep errors typed and content-free at all command boundaries.
func ErrorCode(err error) string {
	var code Refusal
	if errors.As(err, &code) { return string(code) }
	return "RECOVERY_HOLD_INTERNAL"
}
