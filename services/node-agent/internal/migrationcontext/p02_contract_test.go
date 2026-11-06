package migrationcontext

import (
	"bytes"
	"encoding/json"
	"reflect"
	"sort"
	"strconv"
	"testing"
)

// Test-only complete deterministic reflection fingerprint. Production has no
// reflection or interface/callback injection. Pointer identities are excluded.
func p02TestFingerprint(v reflect.Value, b *bytes.Buffer) {
	if !v.IsValid() {
		b.WriteString("invalid;")
		return
	}
	b.WriteString(v.Type().String())
	b.WriteByte(':')
	switch v.Kind() {
	case reflect.Pointer:
		if v.IsNil() {
			b.WriteString("nil;")
		} else {
			p02TestFingerprint(v.Elem(), b)
		}
	case reflect.Struct:
		for i := 0; i < v.NumField(); i++ {
			b.WriteString(v.Type().Field(i).Name)
			p02TestFingerprint(v.Field(i), b)
		}
	case reflect.Slice, reflect.Array:
		if v.Kind() == reflect.Slice && v.IsNil() {
			b.WriteString("nil;")
		}
		b.WriteString(strconv.Itoa(v.Len()))
		for i := 0; i < v.Len(); i++ {
			p02TestFingerprint(v.Index(i), b)
		}
	case reflect.Map:
		if v.IsNil() {
			b.WriteString("nil;")
		}
		keys := v.MapKeys()
		sort.Slice(keys, func(i, j int) bool { return keys[i].String() < keys[j].String() })
		for _, k := range keys {
			p02TestFingerprint(k, b)
			p02TestFingerprint(v.MapIndex(k), b)
		}
	case reflect.String:
		b.WriteString(strconv.Quote(v.String()))
	case reflect.Bool:
		b.WriteString(strconv.FormatBool(v.Bool()))
	case reflect.Int, reflect.Int64:
		b.WriteString(strconv.FormatInt(v.Int(), 10))
	case reflect.Uint8:
		b.WriteString(strconv.FormatUint(v.Uint(), 10))
	default:
		panic("test fingerprint: unexpected open type")
	}
	b.WriteByte(';')
}
func p02TestHash(v p02TestInput) string {
	var b bytes.Buffer
	p02TestFingerprint(reflect.ValueOf(v), &b)
	return hashBytes(b.Bytes())
}
func p02TestEncode(t *testing.T, v p02Value, c2 bool) []byte {
	t.Helper()
	b, ok := p02Encode(v, c2)
	if !ok {
		t.Fatal("test setup canonical encoding")
	}
	return b
}
func p02TestWire(t *testing.T, tc p02TestInput) (p02Envelope, p02Payload) {
	t.Helper()
	e, ok := p02Decode(tc.raw, p02EnvelopeLimit, false)
	if !ok || !p02EnvelopeSchema(e) {
		t.Fatal("test setup envelope")
	}
	p, ok := p02Decode(tc.payload, p02PayloadLimit, false)
	if !ok || !p02PayloadSchema(p) {
		t.Fatal("test setup payload")
	}
	return p02ReadEnvelope(e), p02ReadPayload(p)
}
func p02TestToken(in p02Inputs) p02SnapshotToken {
	return p02SnapshotToken{revision: "SYNTHETIC_SNAPSHOT_1", capsuleSHA256: hashBytes(in.capsuleRaw), generation: in.capsule.generation, selector: in.capsule.selector, scopeSHA256: in.capsule.scopeSHA256, recordIdentity: in.lifecycle.currentRecordIdentity, recordVersion: in.lifecycle.currentVersion, ticketID: in.ticket.id, measurementSHA256: hashBytes(in.measurement.rawEvidence)}
}
func p02TestTuple(e p02Envelope, input []byte, sig []byte) p02SignatureTuple {
	b := e.body
	return p02SignatureTuple{format: b.format, purpose: b.purpose, domain: p02Domain, keySPKI: e.signer.keySPKISHA256, capsuleSHA256: b.capsuleSHA256, generation: b.provisioningGeneration, selector: b.selector, scopeSHA256: b.scopeSHA256, anchorVersion: b.anchorVersion, recordVersion: b.recordVersion, requestBindingSHA256: b.requestBindingSHA256, signingInput: copyBytes(input), signature: copyBytes(sig)}
}

// Explicit adversarial rebinding of private SYNTHETIC hypotheses only. It is
// never a signer, authority/loader, or production acquisition implementation.
func p02TestRebind(t *testing.T, tc p02TestInput, e p02Envelope, p p02Payload) p02TestInput {
	t.Helper()
	in := tc.in
	in.capsuleRaw = p02TestEncode(t, p02ValueCapsule(*in.capsule), false)
	in.measurement.rawEvidence = p02TestEncode(t, p02ValueMeasurement(*in.measurement), false)
	e.body.capsuleSHA256 = hashBytes(in.capsuleRaw)
	e.body.facts.policyPayloadSHA256 = hashBytes(p02TestEncode(t, p02ValuePayload(p), false))
	in.source.facts.policyPayloadSHA256 = e.body.facts.policyPayloadSHA256
	st := in.coverage.statement
	e.body.facts.reviewCoverageSHA256 = p02CanonicalHash(p02ValueCoverageStatement(st), true)
	e.body.facts.sourceEquivalenceSHA256 = p02CanonicalHash(p02Get(p02ValueCoverageStatement(st), "parts"), true)
	e.body.facts.rootChoiceSHA256 = hashBytes(in.coverage.rawEvidence)
	in.source.facts.reviewCoverageSHA256 = e.body.facts.reviewCoverageSHA256
	in.source.facts.sourceEquivalenceSHA256 = e.body.facts.sourceEquivalenceSHA256
	in.source.facts.rootChoiceSHA256 = e.body.facts.rootChoiceSHA256
	in.lifecycle.currentRecordIdentity = p02RecordIdentity(p02ValueEnvelope(e))
	in.lifecycle.capsuleSHA256 = e.body.capsuleSHA256
	in.ticket.capsuleSHA256 = e.body.capsuleSHA256
	in.ticket.currentRecordIdentity = in.lifecycle.currentRecordIdentity
	c := p02Context{in: in}
	e.body.facts.runningMeasurementSHA256 = hashBytes(in.measurement.rawEvidence)
	e.body.requestBindingSHA256 = p02CanonicalHash(c.requestProjection(), true)
	ev := p02ValueEnvelope(e)
	raw := p02TestEncode(t, ev, false)
	c.envelopeValue = ev
	c.envelope = e
	sig, ok := p02Unhex(e.signatureHex)
	if !ok {
		t.Fatal("test setup signature")
	}
	in.signatures = []p02SignatureTuple{p02TestTuple(e, c.signingInput(), sig)}
	in.before = p02TestToken(in)
	in.after = in.before
	return p02TestInput{raw: raw, payload: p02TestEncode(t, p02ValuePayload(p), false), artifact: tc.artifact, in: in}
}
func p02TestCheck(t *testing.T, id string, tc p02TestInput, reason, stage, detail string, bound bool) p02Result {
	t.Helper()
	before := p02TestHash(tc)
	if bound {
		ev, ok := p02Decode(tc.raw, p02EnvelopeLimit, false)
		if !ok || !p02EnvelopeSchema(ev) {
			t.Fatal(id, "semantic kill lacks valid canonical envelope")
		}
		pv, ok := p02Decode(tc.payload, p02PayloadLimit, false)
		if !ok || !p02PayloadSchema(pv) {
			t.Fatal(id, "semantic kill lacks valid canonical payload")
		}
		e := p02ReadEnvelope(ev)
		if hashBytes(tc.payload) != e.body.facts.policyPayloadSHA256 {
			t.Fatal(id, "semantic kill lacks bound payload digest")
		}
		c := p02Context{in: tc.in, envelope: e, envelopeValue: ev}
		if !c.signature() {
			t.Fatal(id, "semantic kill lacks exact tuple/context binding", c.result)
		}
	}
	r := p02Evaluate(tc.raw, tc.payload, tc.artifact, tc.in)
	if r.reason != reason || r.stage != stage || detail != "" && r.detail != detail {
		t.Fatalf("%s cause want %s/%s/%s got %s/%s/%s", id, reason, stage, detail, r.reason, r.stage, r.detail)
	}
	stages := p02Stages()
	n := len(stages)
	if stage != "" {
		for i, s := range stages {
			if s == stage {
				n = i
				break
			}
		}
	}
	if !reflect.DeepEqual(r.passed, stages[:n]) && !(n == 0 && len(r.passed) == 0) {
		t.Fatalf("%s earlier-stage prefix got %v want %v", id, r.passed, stages[:n])
	}
	if r.publicRefusal().(*Refusal).Code() != TrustUnknown {
		t.Fatal("private consistency became public authority")
	}
	after := p02TestHash(tc)
	if before != after {
		t.Fatal(id, "evaluation mutated input")
	}
	t.Logf("P02_CASE id=%s beforeSHA256=%s afterSHA256=%s stage=%s reason=%s prior=%d actualAuth=false", id, before, after, r.stage, r.reason, len(r.passed))
	return r
}
func p02TestBound(t *testing.T, id string, tc p02TestInput, reason, stage, detail string) p02Result {
	return p02TestCheck(t, id, tc, reason, stage, detail, true)
}
func TestP02InternalApprovalContract(t *testing.T) {
	p02TestBound(t, "C01", p02BenignFixture(), "", "", "")
	for _, id := range []string{"W03-V19", "W04-V20", "W05-V20b"} {
		t.Run(id, func(t *testing.T) {
			tc := p02BenignFixture()
			e, p := p02TestWire(t, tc)
			expected := "effective-publication-distinct-from-every-original-and-part"
			if id == "W03-V19" {
				bad := "SYNTHETIC_REVISION_REQUIRED_NOT_APPROVED"
				tc.in.coverage.statement.effective.verdict = bad
				e.body.facts.effectiveReviewVerdict = bad
				tc.in.source.facts.effectiveReviewVerdict = bad
				expected = "independently-approved-effective-verdict"
			} else {
				idx := 1
				if id == "W05-V20b" {
					idx = 0
				}
				old := e.body.reviews[idx].reviewSHA
				tc.in.coverage.statement.effective.publicationSHA = old
				p.verifier.reviewSHA = old
				e.body.facts.effectiveReviewSHA = old
				tc.in.source.facts.effectiveReviewSHA = old
			}
			original := append([]p02Review(nil), e.body.reviews...)
			tc = p02TestRebind(t, tc, e, p)
			if !reflect.DeepEqual(tc.in.reviews.reviews, original) {
				t.Fatal("original reviews rewritten")
			}
			p02TestBound(t, id, tc, "PROVENANCE", "05_REVIEWS", expected)
		})
	}
	for _, n := range []int{0, 128, 129} {
		t.Run("length-"+strconv.Itoa(n), func(t *testing.T) {
			tc := p02BenignFixture()
			e, p := p02TestWire(t, tc)
			v := string(bytes.Repeat([]byte{'A'}, n))
			tc.in.capsule.expectedEffectiveVerdict.literal = v
			// Empty effective verdict is forbidden by the envelope schema, so only the
			// independent expectation is emptied in the predicate-negative case.
			if n > 0 {
				tc.in.coverage.statement.effective.verdict = v
				e.body.facts.effectiveReviewVerdict = v
				tc.in.source.facts.effectiveReviewVerdict = v
			}
			tc = p02TestRebind(t, tc, e, p)
			if n == 128 {
				p02TestBound(t, "expect-128", tc, "", "", "")
			} else {
				p02TestBound(t, "expect-length-"+strconv.Itoa(n), tc, "PROVENANCE", "05_REVIEWS", "closed-independent-effective-verdict-expectation")
			}
		})
	}
	for _, k := range []byte{'i', 'b', 'n', 'a', 'o'} {
		t.Run("type-"+string(k), func(t *testing.T) {
			tc := p02BenignFixture()
			e, p := p02TestWire(t, tc)
			tc.in.capsule.expectedEffectiveVerdict.kind = k
			tc.in.capsule.expectedEffectiveVerdict.integer = 7
			tc = p02TestRebind(t, tc, e, p)
			p02TestBound(t, "expect-type-"+string(k), tc, "PROVENANCE", "05_REVIEWS", "closed-independent-effective-verdict-expectation")
		})
	}
	t.Run("missing", func(t *testing.T) {
		tc := p02BenignFixture()
		e, p := p02TestWire(t, tc)
		tc.in.capsule.expectedEffectiveVerdict.present = false
		tc = p02TestRebind(t, tc, e, p)
		p02TestBound(t, "expect-missing", tc, "ANCHOR", "01_ANCHOR", "closed-capsule-descriptor")
	})
	for _, bad := range []string{"bad\nvalue", "bad\u00e9value"} {
		t.Run(strconv.Quote(bad), func(t *testing.T) {
			tc := p02BenignFixture()
			v := map[string]json.RawMessage{}
			if err := json.Unmarshal(tc.in.capsuleRaw, &v); err != nil {
				t.Fatal(err)
			}
			b, _ := json.Marshal(bad)
			v["expectedEffectiveVerdict"] = b
			raw, err := json.Marshal(v)
			if err != nil {
				t.Fatal(err)
			}
			tc.in.capsuleRaw = raw
			tc.in.capsule.expectedEffectiveVerdict.literal = bad
			// Only the capsule codec is targeted, before the scope/signature stage.
			p02TestCheck(t, "expect-nonprintable", tc, "ANCHOR", "01_ANCHOR", "capsule-unavailable", false)
		})
	}
	t.Run("not-a-source-SHA-distinctness-rule", func(t *testing.T) {
		tc := p02BenignFixture()
		e, p := p02TestWire(t, tc)
		v := tc.in.source.facts.sourceSHA
		tc.in.coverage.statement.effective.publicationSHA = v
		e.body.facts.effectiveReviewSHA = v
		p.verifier.reviewSHA = v
		tc.in.source.facts.effectiveReviewSHA = v
		tc = p02TestRebind(t, tc, e, p)
		p02TestBound(t, "P02R3-I2", tc, "", "", "")
	})
}

func TestP02InternalOriginalScopeRawUTF8(t *testing.T) {
	tc := p02BenignFixture()
	e, p := p02TestWire(t, tc)
	raw := []byte("Original scope \uac80\ud1a0\nexact bytes")
	e.body.reviews[0].scopeUTF8Hex = hexForTest(raw)
	e.body.reviews[0].scopeSHA256 = hashBytes(raw)
	tc.in.reviews.reviews = append([]p02Review(nil), e.body.reviews...)
	tc.in.coverage.statement.reviewSetSHA256 = p02CanonicalHash(p02ValuesReviews(e.body.reviews), true)
	tc = p02TestRebind(t, tc, e, p)
	p02TestBound(t, "original-raw-UTF8-scope", tc, "", "", "")
}
