package migrationcontext

import (
	"bytes"
	"crypto/ed25519"
	"crypto/sha256"
	"crypto/x509"
	"encoding/hex"
	"encoding/json"
	"reflect"
	"strconv"
	"strings"
	"testing"
)

// PUBLIC NONSECRET TEST VECTOR, not a credential. Crypto executes only when
// Root runs these tests in the separately authorized isolated Go environment.
var h12PublicTestSeed = [32]byte{1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32}

const h12ExpectedTestDomain = "fleet5/p02/installed-policy-registry/candidate/v2"

type h12TestInput struct {
	raw, der, signedMessage, sig []byte
	expected                     string
	public                       ed25519.PublicKey
}

func h12JSON(t *testing.T, v any) []byte {
	t.Helper()
	b, e := json.Marshal(v)
	if e != nil {
		t.Fatal(e)
	}
	return b
}
func h12Object(t *testing.T, raw []byte) map[string]json.RawMessage {
	t.Helper()
	var v map[string]json.RawMessage
	if e := json.Unmarshal(raw, &v); e != nil {
		t.Fatal(e)
	}
	return v
}
func h12String(t *testing.T, v json.RawMessage) string {
	t.Helper()
	var s string
	if e := json.Unmarshal(v, &s); e != nil {
		t.Fatal(e)
	}
	return s
}
func h12Integer(t *testing.T, v json.RawMessage) int64 {
	t.Helper()
	var n int64
	if e := json.Unmarshal(v, &n); e != nil {
		t.Fatal(e)
	}
	return n
}

// Independent signing oracle: stdlib canonical fixture JSON, fixed literal
// domain + NUL + WHOLE body/signer. Never calls the helper or signingInput().
func h12OracleMessage(t *testing.T, raw []byte) []byte {
	t.Helper()
	env := h12Object(t, raw)
	wrapper := struct {
		Body   json.RawMessage `json:"body"`
		Signer json.RawMessage `json:"signer"`
	}{env["body"], env["signer"]}
	out := append([]byte(h12ExpectedTestDomain), 0)
	return append(out, h12JSON(t, wrapper)...)
}
func h12Wire(t *testing.T, body map[string]json.RawMessage, signer string, sig []byte) []byte {
	t.Helper()
	return h12JSON(t, map[string]any{"body": body, "signer": map[string]string{"keySPKISHA256": signer}, "signatureHex": hex.EncodeToString(sig)})
}
func h12Fixture(t *testing.T, derOverride []byte, differentBody bool, mode string) h12TestInput {
	t.Helper()
	key := ed25519.NewKeyFromSeed(h12PublicTestSeed[:])
	pub := key.Public().(ed25519.PublicKey)
	der, e := x509.MarshalPKIXPublicKey(pub)
	if e != nil {
		t.Fatal(e)
	}
	if derOverride != nil {
		der = copyBytes(derOverride)
	}
	expected := hashBytes(der)
	env := h12Object(t, p02BenignFixture().raw)
	body := h12Object(t, env["body"])
	if differentBody {
		body["selector"] = h12JSON(t, "mathematically-valid-other-policy")
	}
	raw := h12Wire(t, body, expected, make([]byte, 64))
	msg := h12OracleMessage(t, raw)
	switch mode {
	case "wrong-domain":
		msg = append(append([]byte("wrong/fleet5/domain"), 0), msg[len(h12ExpectedTestDomain)+1:]...)
	case "missing-NUL":
		msg = append([]byte(h12ExpectedTestDomain), msg[len(h12ExpectedTestDomain)+1:]...)
	case "hash-only":
		h := sha256.Sum256(msg)
		msg = copyBytes(h[:])
	case "body-only":
		msg = append(append([]byte(h12ExpectedTestDomain), 0), h12JSON(t, body)...)
	case "wrong-key":
		seed := h12PublicTestSeed
		seed[0] ^= 0x40
		key = ed25519.NewKeyFromSeed(seed[:])
	}
	sig := ed25519.Sign(key, msg)
	if !ed25519.Verify(key.Public().(ed25519.PublicKey), msg, sig) {
		t.Fatal("independent signing oracle failed")
	}
	raw = h12Wire(t, body, expected, sig)
	return h12TestInput{raw: raw, der: copyBytes(der), expected: expected, public: copyBytes(pub), signedMessage: copyBytes(msg), sig: copyBytes(sig)}
}
func h12Rewire(t *testing.T, f h12TestInput, change func(map[string]json.RawMessage)) h12TestInput {
	t.Helper()
	v := h12Object(t, f.raw)
	change(v)
	f.raw = h12JSON(t, v)
	return f
}
func h12Fingerprint(f h12TestInput) string {
	// Exactly the three function arguments; fixture labels/oracles excluded.
	var b bytes.Buffer
	for _, v := range [][]byte{f.raw, f.der, []byte(f.expected)} {
		b.WriteString(strconv.Itoa(len(v)))
		b.WriteByte(':')
		b.Write(v)
	}
	return hashBytes(b.Bytes())
}
func h12TupleHash(v p02SignatureTuple) string {
	var b bytes.Buffer
	p02TestFingerprint(reflect.ValueOf(v), &b)
	return hashBytes(b.Bytes())
}
func h12ExpectedTuple(t *testing.T, f h12TestInput) p02SignatureTuple {
	t.Helper()
	env := h12Object(t, f.raw)
	b := h12Object(t, env["body"])
	sig, e := hex.DecodeString(h12String(t, env["signatureHex"]))
	if e != nil {
		t.Fatal(e)
	}
	return p02SignatureTuple{format: h12String(t, b["format"]), purpose: h12String(t, b["purpose"]), domain: h12ExpectedTestDomain, keySPKI: f.expected, capsuleSHA256: h12String(t, b["capsuleSHA256"]), generation: h12String(t, b["provisioningGeneration"]), selector: h12String(t, b["selector"]), scopeSHA256: h12String(t, b["scopeSHA256"]), requestBindingSHA256: h12String(t, b["requestBindingSHA256"]), anchorVersion: h12Integer(t, b["anchorVersion"]), recordVersion: h12Integer(t, b["recordVersion"]), signingInput: h12OracleMessage(t, f.raw), signature: sig}
}
func h12MathPreconditions(t *testing.T, f h12TestInput) {
	t.Helper()
	v, ok := p02Decode(f.raw, p02EnvelopeLimit, false)
	if !ok || !p02EnvelopeSchema(v) {
		t.Fatal("math case lacks independently checked canonical/schema preconditions")
	}
	signer := h12Object(t, h12Object(t, f.raw)["signer"])
	if len(f.expected) != 64 || h12String(t, signer["keySPKISHA256"]) != f.expected || hashBytes(f.der) != f.expected {
		t.Fatal("math case lacks exact earlier DER/key binding")
	}
	// The known fixture public key and standard signature oracle establish key
	// size and the independently signed ORIGINAL message, not target acceptance.
	if len(f.public) != 32 || len(f.sig) != 64 {
		t.Fatal("math key/signature length precondition")
	}
	canonicalDER, err := x509.MarshalPKIXPublicKey(f.public)
	if err != nil || !bytes.Equal(canonicalDER, f.der) {
		t.Fatal("math case lacks independently canonical expected-key DER")
	}
}

func TestH12SignatureMathAndCanonicalBoundary(t *testing.T) {
	base := h12Fixture(t, nil, false, "")
	cases := []struct {
		name, layer string
		in          h12TestInput
		want        bool
	}{{"valid-whole-message", "math", base, true}, {"resigned-other-policy-math-only", "math", h12Fixture(t, nil, true, ""), true}}
	for _, mode := range []string{"wrong-key", "wrong-domain", "missing-NUL", "hash-only", "body-only"} {
		cases = append(cases, struct {
			name, layer string
			in          h12TestInput
			want        bool
		}{mode, "math", h12Fixture(t, nil, false, mode), false})
	}
	changed := h12Rewire(t, base, func(v map[string]json.RawMessage) {
		b := h12Object(t, v["body"])
		b["selector"] = h12JSON(t, "canonical-body-changed-without-resigning")
		v["body"] = h12JSON(t, b)
	})
	cases = append(cases, struct {
		name, layer string
		in          h12TestInput
		want        bool
	}{"body-changed-without-resign", "math", changed, false})
	tampered := h12Rewire(t, base, func(v map[string]json.RawMessage) {
		sig := copyBytes(base.sig)
		sig[63] ^= 1
		v["signatureHex"] = h12JSON(t, hex.EncodeToString(sig))
	})
	cases = append(cases, struct {
		name, layer string
		in          h12TestInput
		want        bool
	}{"tampered-signature", "math", tampered, false})
	add := func(name, layer string, f h12TestInput) {
		cases = append(cases, struct {
			name, layer string
			in          h12TestInput
			want        bool
		}{name, layer, f, false})
	}
	for _, x := range []struct{ name, hash string }{{"empty-expected", ""}, {"short-expected", strings.Repeat("a", 63)}, {"long-expected", strings.Repeat("a", 65)}, {"uppercase-expected", strings.ToUpper(base.expected)}, {"invalid-expected", strings.Repeat("g", 64)}, {"wrong-expected", strings.Repeat("0", 64)}} {
		f := base
		f.expected = x.hash
		add(x.name, "expected-key", f)
	}
	rawHash := base
	rawHash.expected = hashBytes(base.public)
	add("raw-key-hash-not-SPKI", "expected-key", rawHash)
	emptyDER := base
	emptyDER.der = nil
	add("empty-DER", "admission", emptyDER)
	hugeDER := base
	hugeDER.der = bytes.Repeat([]byte{0}, 4097)
	add("oversize-DER", "admission", hugeDER)
	add("malformed-DER-rebound", "DER", h12Fixture(t, []byte{0x30, 0x00}, false, ""))
	trailing := append(copyBytes(base.der), 0)
	add("trailing-DER-rebound", "DER", h12Fixture(t, trailing, false, ""))
	if len(base.der) != 44 || !bytes.Equal(base.der[:12], []byte{0x30, 0x2a, 0x30, 0x05, 0x06, 0x03, 0x2b, 0x65, 0x70, 0x03, 0x21, 0x00}) {
		t.Fatal("fixture Ed25519 SPKI structural precondition")
	}
	wrongAlg := copyBytes(base.der)
	wrongAlg[8] = 0x6e
	add("wrong-algorithm-rebound", "DER", h12Fixture(t, wrongAlg, false, ""))
	nullDER := append([]byte{0x30, 0x2c, 0x30, 0x07, 0x06, 0x03, 0x2b, 0x65, 0x70, 0x05, 0x00, 0x03, 0x21, 0x00}, base.der[12:]...)
	add("NULL-parameter-DER-rebound", "DER", h12Fixture(t, nullDER, false, ""))
	alternate := append([]byte{0x30, 0x81, 0x2a}, base.der[2:]...)
	add("nonminimal-DER-rebound", "DER", h12Fixture(t, alternate, false, ""))
	for _, n := range []int{63, 65} {
		f := h12Rewire(t, base, func(v map[string]json.RawMessage) { v["signatureHex"] = h12JSON(t, strings.Repeat("aa", n)) })
		add("signature-bytes-"+strconv.Itoa(n), "codec/signature-encoding", f)
	}
	for _, x := range []struct {
		name string
		raw  []byte
	}{{"empty-record", nil}, {"oversize-record", bytes.Repeat([]byte{' '}, p02EnvelopeLimit+1)}, {"noncanonical-whitespace", append([]byte(" "), base.raw...)}, {"trailing-record", append(copyBytes(base.raw), '\n')}, {"duplicate-field", append([]byte(`{"body":null,`), base.raw[1:]...)}, {"invalid-UTF8", []byte{'{', '"', 0xff, '"', ':', '1', '}'}}, {"depth-bound", []byte(strings.Repeat("[", 70) + "0" + strings.Repeat("]", 70))}} {
		f := base
		f.raw = x.raw
		add(x.name, "admission/codec", f)
	}
	seen := map[string]string{}
	for _, x := range cases {
		t.Run(x.name, func(t *testing.T) {
			before := h12Fingerprint(x.in)
			if prior, ok := seen[before]; ok {
				t.Fatal("duplicate complete input", prior, x.name)
			}
			seen[before] = x.name
			if x.layer == "math" {
				h12MathPreconditions(t, x.in)
				env := h12Object(t, x.in.raw)
				wireSignature, err := hex.DecodeString(h12String(t, env["signatureHex"]))
				if err != nil || len(wireSignature) != 64 || ed25519.Verify(x.in.public, h12OracleMessage(t, x.in.raw), wireSignature) != x.want {
					t.Fatal("independent target-message oracle/precondition differs")
				}
			}
			if x.name == "depth-bound" {
				if _, ok := p02Decode(x.in.raw, p02EnvelopeLimit, false); ok {
					t.Fatal("depth case must fail the bounded parser, not merely envelope schema")
				}
			}
			if x.layer == "DER" {
				v, ok := p02Decode(x.in.raw, p02EnvelopeLimit, false)
				if !ok || !p02EnvelopeSchema(v) || hashBytes(x.in.der) != x.in.expected {
					t.Fatal("DER case failed an earlier codec/key precondition")
				}
			}
			got, ok := h12CheckRegistrySignature(x.in.raw, x.in.der, x.in.expected)
			if ok != x.want {
				t.Fatal("wrong math/canonical outcome", x.layer, ok)
			}
			if ok {
				if !reflect.DeepEqual(got, h12ExpectedTuple(t, x.in)) {
					t.Fatal("not exact13field tuple")
				}
				if !ed25519.Verify(x.in.public, got.signingInput, got.signature) {
					t.Fatal("independent full-message signature oracle")
				}
			} else if !reflect.DeepEqual(got, p02SignatureTuple{}) {
				t.Fatal("failure leaked nonzero tuple")
			}
			after := h12Fingerprint(x.in)
			if before != after {
				t.Fatal("helper mutated supplied arguments")
			}
			t.Logf("H12_CASE id=%s layer=%s beforeSHA256=%s afterSHA256=%s math=%t actualAuthority=false", x.name, x.layer, before, after, ok)
		})
	}
	// A separate public call cannot consume this private math result as trust.
	policy, err := NewService().LoadInstalledPolicy("deployment")
	if policy != nil {
		t.Fatal("math issued public policy")
	}
	wantCode(t, err, TrustUnknown)
}

func TestH12SignatureOwnedOutputAndAdmission(t *testing.T) {
	f := h12Fixture(t, nil, false, "")
	got, ok := h12CheckRegistrySignature(f.raw, f.der, f.expected)
	if !ok {
		t.Fatal("ownership control")
	}
	before := h12TupleHash(got)
	for i := range f.raw {
		f.raw[i] ^= 0xff
	}
	for i := range f.der {
		f.der[i] ^= 0xff
	}
	if h12TupleHash(got) != before {
		t.Fatal("returned tuple aliases original raw/DER")
	}
	// Reuse exactly the table's oversize-record arguments; these repeated
	// evaluations are NOT additional distinct complete inputs.
	over := h12Fixture(t, nil, false, "")
	over.raw = bytes.Repeat([]byte{' '}, p02EnvelopeLimit+1)
	var result p02SignatureTuple
	var success bool
	allocations := testing.AllocsPerRun(1, func() { result, success = h12CheckRegistrySignature(over.raw, over.der, over.expected) })
	if allocations != 0 || success || !reflect.DeepEqual(result, p02SignatureTuple{}) {
		t.Fatal("admission copied/parsed oversized record", allocations)
	}
	t.Logf("H12_ADMISSION allocations=%g repeatedEvaluations=2 uniqueAdditionalInputs=0 inputSHA256=%s tableCase=oversize-record actualAuthority=false", allocations, h12Fingerprint(over))
}
