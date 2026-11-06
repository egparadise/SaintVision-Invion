package migrationcontext

import (
	"bytes"
	"testing"
)

func TestP02InternalStrictLexicalCodec(t *testing.T) {
	baseline := p02BenignFixture()
	cases := []struct {
		name string
		raw  []byte
	}{
		{"duplicate", bytes.Replace(baseline.raw, []byte(`"body":{`), []byte(`"body":{"anchorVersion":1,`), 1)},
		{"escaped-key", bytes.Replace(baseline.raw, []byte(`"body"`), []byte(`"b\u006fdy"`), 1)},
		{"escaped-value", bytes.Replace(baseline.raw, []byte(`"synthetic_legacy_two"`), []byte(`"synthetic_legacy_tw\u006f"`), 1)},
		{"fraction", bytes.Replace(baseline.raw, []byte(`"anchorVersion":1`), []byte(`"anchorVersion":1.0`), 1)},
		{"exponent", bytes.Replace(baseline.raw, []byte(`"anchorVersion":1`), []byte(`"anchorVersion":1e0`), 1)},
		{"minus-zero", bytes.Replace(baseline.raw, []byte(`"anchorVersion":1`), []byte(`"anchorVersion":-0`), 1)},
		{"overflow-safe-integer", bytes.Replace(baseline.raw, []byte(`"anchorVersion":1`), []byte(`"anchorVersion":9007199254740992`), 1)},
		{"overflow-int64", bytes.Replace(baseline.raw, []byte(`"anchorVersion":1`), []byte(`"anchorVersion":9223372036854775808`), 1)},
		{"bool-is-not-int", bytes.Replace(baseline.raw, []byte(`"anchorVersion":1`), []byte(`"anchorVersion":true`), 1)},
		{"null", bytes.Replace(baseline.raw, []byte(`"anchorVersion":1`), []byte(`"anchorVersion":null`), 1)},
		{"missing", bytes.Replace(baseline.raw, []byte(`"anchorVersion":1,`), nil, 1)},
		{"whitespace", append([]byte{' '}, baseline.raw...)},
		{"trailing-LF", append(copyBytes(baseline.raw), '\n')},
		{"trailing-CRLF", append(copyBytes(baseline.raw), '\r', '\n')},
		{"multiple-values", append(copyBytes(baseline.raw), '{', '}')},
		{"BOM", append([]byte{0xef, 0xbb, 0xbf}, baseline.raw...)},
		{"surrogate-alias", bytes.Replace(baseline.raw, []byte(`"synthetic_legacy_two"`), []byte(`"x\ud800"`), 1)},
		{"escaped-control", bytes.Replace(baseline.raw, []byte(`"synthetic_legacy_two"`), []byte(`"x\n"`), 1)},
		{"uppercase-hex", bytes.Replace(baseline.raw, []byte(`"sourceSHA":"b1`), []byte(`"sourceSHA":"B1`), 1)},
	}
	for _, x := range cases {
		t.Run(x.name, func(t *testing.T) {
			tc := p02BenignFixture()
			if bytes.Equal(x.raw, baseline.raw) {
				t.Fatal("codec mutant did not change actual input")
			}
			tc.raw = x.raw
			p02TestCheck(t, "codec-"+x.name, tc, "FORMAT", "03_ENVELOPE", "closed-envelope-canonical-schema", false)
		})
	}
	t.Run("unknown-key", func(t *testing.T) {
		tc := p02BenignFixture()
		v, ok := p02Decode(tc.raw, p02EnvelopeLimit, false)
		if !ok {
			t.Fatal("setup")
		}
		v.object = append(v.object, p02Field{"unknown", p02Integer(1)})
		tc.raw = p02TestEncode(t, v, false)
		p02TestCheck(t, "codec-unknown", tc, "FORMAT", "03_ENVELOPE", "closed-envelope-canonical-schema", false)
	})
	t.Run("envelope-budget-before-copy", func(t *testing.T) {
		tc := p02BenignFixture()
		tc.raw = make([]byte, p02EnvelopeLimit+1)
		p02TestCheck(t, "envelope-budget", tc, "FORMAT", "03_ENVELOPE", "envelope-byte-budget", false)
	})
	for _, n := range []int{32, 33} {
		raw := append(bytes.Repeat([]byte{'['}, n), '0')
		raw = append(raw, bytes.Repeat([]byte{']'}, n)...)
		_, ok := p02Decode(raw, p02EnvelopeLimit, false)
		if ok != (n == 32) {
			t.Fatalf("depth boundary %d=%v", n, ok)
		}
	}
	for _, n := range []int{99999, 100000} {
		raw := []byte{'['}
		for i := 0; i < n; i++ {
			if i > 0 {
				raw = append(raw, ',')
			}
			raw = append(raw, '0')
		}
		raw = append(raw, ']')
		_, ok := p02Decode(raw, p02EnvelopeLimit, false)
		if ok != (n == 99999) {
			t.Fatalf("node boundary %d=%v", n, ok)
		}
	}
}
func TestP02InternalC2AndEpochDomains(t *testing.T) {
	raw := []byte(`{"class":"COMPONENT","component":"synthetic\u0026helper"}`)
	v, ok := p02Decode(raw, 65536, true)
	if !ok || !p02AuthoritySchema(v) {
		t.Fatal("C2 escaped HTML control")
	}
	for _, bad := range [][]byte{bytes.Replace(raw, []byte(`\u0026`), []byte(`&`), 1), bytes.Replace(raw, []byte(`\u0026`), []byte(`\u0026\u000a`), 1), []byte(`{"class":"UNKNOWN","component":"x"}`)} {
		v, ok := p02Decode(bad, 65536, true)
		if ok && p02AuthoritySchema(v) {
			t.Fatal("C2 alias or unknown class accepted")
		}
	}
	for _, n := range []int64{-1, 0, p02MaxEpoch, p02MaxEpoch + 1} {
		if p02Epoch(n) != (n >= 0 && n <= p02MaxEpoch) {
			t.Fatal("epoch domain", n)
		}
	}
	if p02Decimal(p02SafeInteger) != "9007199254740991" || p02Decimal(0) != "0" {
		t.Fatal("canonical decimal IDs")
	}
}
func TestP02InternalEightComponentsAndArtifact(t *testing.T) {
	for _, name := range []string{"graph", "contractSet", "semanticPins", "cohort", "keyGrants", "proofSlots", "registration", "nodeKinds"} {
		t.Run(name, func(t *testing.T) {
			tc := p02BenignFixture()
			e, p := p02TestWire(t, tc)
			bad := string(bytes.Repeat([]byte("af"), 32))
			switch name {
			case "graph":
				p.graphHex = "00"
			case "contractSet":
				e.body.facts.contractSetSHA256 = bad
				tc.in.source.facts.contractSetSHA256 = bad
			case "semanticPins":
				p.semanticPins.k1SourcePinSetSHA256 = bad
			case "cohort":
				e.body.facts.cohortScopeSHA256 = bad
				tc.in.source.facts.cohortScopeSHA256 = bad
			case "keyGrants":
				e.body.facts.keyGrantsSHA256 = bad
				tc.in.source.facts.keyGrantsSHA256 = bad
			case "proofSlots":
				p.proofSlotRegistryHex = "00"
			case "registration":
				reg, _ := p02Unhex(p.designRegistrationHex)
				p.designRegistrationHex = hexForTest(bytes.ReplaceAll(reg, []byte("\r\n"), []byte("\n")))
			case "nodeKinds":
				p.nodeKinds["synthetic-kind"] = "OTHER"
			}
			tc = p02TestRebind(t, tc, e, p)
			p02TestBound(t, "components-"+name, tc, "PROVENANCE", "05_COMPONENTS", "")
		})
	}
	tc := p02BenignFixture()
	tc.artifact[0] ^= 1
	p02TestBound(t, "archive-not-executable", tc, "ARTIFACT", "05_ARTIFACT", "exact-downloaded-archive-digest")
}
func hexForTest(b []byte) string {
	const digits = "0123456789abcdef"
	out := make([]byte, 0, len(b)*2)
	for _, c := range b {
		out = append(out, digits[c>>4], digits[c&15])
	}
	return string(out)
}
