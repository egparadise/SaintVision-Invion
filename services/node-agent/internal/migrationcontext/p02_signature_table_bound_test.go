package migrationcontext

import (
	"reflect"
	"strconv"
	"testing"
)

func TestP02InternalSignatureTableBound(t *testing.T) {
	for _, n := range []int{16, 17} {
		t.Run(strconv.Itoa(n), func(t *testing.T) {
			tc := p02BenignFixture()
			valid := p02FreezeSignatureTuple(tc.in.signatures[0])
			tc.in.signatures = make([]p02SignatureTuple, 0, n)
			for i := 1; i < n; i++ {
				extra := p02FreezeSignatureTuple(valid)
				extra.signature[len(extra.signature)-1] ^= byte(i)
				tc.in.signatures = append(tc.in.signatures, extra)
			}
			tc.in.signatures = append(tc.in.signatures, valid)

			// Prove the exact matching synthetic tuple remains LAST, independently
			// of signature()'s table-size guard. No real authentication is claimed.
			ev, ok := p02Decode(tc.raw, p02EnvelopeLimit, false)
			if !ok || !p02EnvelopeSchema(ev) {
				t.Fatal("invalid canonical envelope precondition")
			}
			pv, ok := p02Decode(tc.payload, p02PayloadLimit, false)
			if !ok || !p02PayloadSchema(pv) {
				t.Fatal("invalid canonical payload precondition")
			}
			e := p02ReadEnvelope(ev)
			if hashBytes(tc.payload) != e.body.facts.policyPayloadSHA256 {
				t.Fatal("unbound payload precondition")
			}
			c := p02Context{in: tc.in, envelope: e, envelopeValue: ev}
			sig, ok := p02Unhex(e.signatureHex)
			want := p02TestTuple(e, c.signingInput(), sig)
			if !ok || len(tc.in.signatures) != n || !reflect.DeepEqual(tc.in.signatures[n-1], want) {
				t.Fatal("matching full-message/context tuple missing")
			}
			for _, extra := range tc.in.signatures[:n-1] {
				if reflect.DeepEqual(extra, want) {
					t.Fatal("unexpected earlier matching tuple")
				}
			}
			c.in.signatures = []p02SignatureTuple{valid}
			if !c.signature() {
				t.Fatal("matching tuple lacks independent capsule/key/domain binding", c.result)
			}

			id := "L1-tuples-" + strconv.Itoa(n)
			if n == 16 {
				p02TestBound(t, id, tc, "", "", "")
				return
			}
			before := p02TestHash(tc)
			p02TestCheck(t, id, tc, "OWNERSHIP", "01_ANCHOR", "immutable-signature-table", false)
			var measured p02Result
			allocations := testing.AllocsPerRun(1, func() {
				measured = p02Evaluate(tc.raw, tc.payload, tc.artifact, tc.in)
			})
			if allocations != 0 || measured.reason != "OWNERSHIP" || measured.stage != "01_ANCHOR" || measured.detail != "immutable-signature-table" || len(measured.passed) != 0 {
				t.Fatalf("oversized table copied/advanced: allocations=%g result=%+v", allocations, measured)
			}
			if after := p02TestHash(tc); before != after {
				t.Fatal("allocation probe mutated input", before, after)
			}
			// One warm-up plus one measured evaluation of the SAME input. These
			// are not additional unique cases and emit no additional P02_CASE rows.
			t.Logf("P02_L1_COPY_BUDGET allocations=%g repeatedEvaluations=2 uniqueAdditionalInputs=0 beforeSHA256=%s afterSHA256=%s actualAuth=false", allocations, before, p02TestHash(tc))
		})
	}
}
