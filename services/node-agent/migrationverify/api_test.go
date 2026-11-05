package migrationverify

import (
	"encoding/json"
	"os"
	"strings"
	"testing"
)

func TestAllCopiedSourcePinsRemainExact(t *testing.T) {
	raw, e := resources.ReadFile("resources/source-pins.json")
	if e != nil {
		t.Fatal(e)
	}
	var m sourceManifest
	if e = json.Unmarshal(raw, &m); e != nil {
		t.Fatal(e)
	}
	if len(m.Pins) != 28 {
		t.Fatal(len(m.Pins))
	}
	for _, p := range m.Pins {
		b, e := os.ReadFile(p.PackagePath)
		if e != nil {
			t.Fatal(e)
		}
		if len(b) != p.RawBytes || shaHex(b) != p.RawSHA256 {
			t.Fatal("frozen input changed", p.Path)
		}
	}
}

func TestAPI2RejectsEveryOldFieldAndNodeCohortTypeConfusion(t *testing.T) {
	s, e := LoadSchemas()
	if e != nil {
		t.Fatal(e)
	}
	g, inputs, payloads, kinds := originalGraph(t)
	old, swapped, schemaRejected, graphRejected := 0, 0, 0, 0
	for id, payload := range payloads {
		kind := kinds[id]
		if kind != "api-request" && kind != "api-response" {
			continue
		}
		p := copyJSON(payload).(map[string]any)
		field := "expectedPriorProjectionSHA256"
		if kind == "api-response" {
			field = "projectionEnvelopeSHA256"
		}
		p[field] = strings.Repeat("f", 64)
		if e = s.Validate(kind, p); e == nil {
			t.Fatal("old ambiguous field accepted", field)
		}
		old++
		p = copyJSON(payload).(map[string]any)
		a, b := "expectedNodeProjectionEnvelopeSHA256", "expectedCohortProjectionSetDigestSHA256"
		if kind == "api-response" {
			a, b = "nodeProjectionEnvelopeSHA256", "cohortProjectionSetDigestSHA256"
		}
		if p[a] == nil && p[b] == nil {
			continue
		}
		p[a], p[b] = p[b], p[a]
		if kind == "api-request" {
			if e = s.Validate(kind, p); e == nil {
				t.Fatal("request Node/cohort swap accepted", id)
			}
			schemaRejected++
		} else {
			payloads[id] = p
			if _, e = g.check(inputs, payloads, kinds); e == nil {
				t.Fatal("response Node/cohort swap accepted by request binding", id)
			}
			payloads[id] = payload
			graphRejected++
		}
		swapped++
	}
	if old != 44 || swapped != 43 || schemaRejected != 21 || graphRejected != 22 {
		t.Fatalf("old=%d swapped=%d schema=%d graph=%d", old, swapped, schemaRejected, graphRejected)
	}
}

func TestDerivedVectorsRejectPartialOrderAndSignerAuthority(t *testing.T) {
	s, e := LoadSchemas()
	if e != nil {
		t.Fatal(e)
	}
	v := fixture(t, "derived-byte-ordering-vectors.json").(map[string]any)
	for _, x := range v["negative"].([]any) {
		x := x.(map[string]any)
		if e = s.Validate("cohort-projection-set", x["body"]); e == nil {
			t.Fatal("invalid derived record accepted", x["label"])
		}
	}
}

func TestCurrentSetRequiresExactExternalCompleteContext(t *testing.T) {
	f := newCryptoFixture(t)
	for name, mutate := range map[string]func(*CurrentProjectionContext){
		"wrong-operation":           func(c *CurrentProjectionContext) { c.OperationID = "foreign" },
		"released-epoch-as-restore": func(c *CurrentProjectionContext) { c.FenceEpoch = 1 },
		"partial-members":           func(c *CurrentProjectionContext) { c.MemberProjectionSHA256 = c.MemberProjectionSHA256[:1] },
		"member-order": func(c *CurrentProjectionContext) {
			c.MemberProjectionSHA256[0], c.MemberProjectionSHA256[1] = c.MemberProjectionSHA256[1], c.MemberProjectionSHA256[0]
		},
		"wrong-head": func(c *CurrentProjectionContext) {
			c.InventoryHead = map[string]any{"presence": "ABSENT", "envelopeSHA256": nil}
		},
		"digest-alone-readback": func(c *CurrentProjectionContext) { c.InventoryReadbackSHA256 = strings.Repeat("e", 64) },
	} {
		t.Run(name, func(t *testing.T) {
			ctx := f.context
			c := *ctx.Current
			c.MemberProjectionSHA256 = append([]string(nil), c.MemberProjectionSHA256...)
			ctx.Current = &c
			mutate(&c)
			v, e := NewVerifier(f.installed, ctx)
			if e != nil {
				t.Fatal(e)
			}
			if _, e = v.VerifyCurrentProjectionSet(f.packet, "cohort-36"); e == nil {
				t.Fatal("ambiguous current context accepted")
			}
		})
	}
}

func TestPacketRejectsExtraUnknownFieldsAndForeignReferents(t *testing.T) {
	f := newCryptoFixture(t)
	v, e := NewVerifier(f.installed, f.context)
	if e != nil {
		t.Fatal(e)
	}
	for name, mutate := range map[string]func(*Packet){
		"foreign-referent": func(p *Packet) { p.Referents[shaHex([]byte("foreign"))] = []byte("foreign") },
		"unknown-clock-override": func(p *Packet) {
			x, e := ParseJSON(p.Records["plan"])
			if e != nil {
				t.Fatal(e)
			}
			x.(map[string]any)["body"].(map[string]any)["nowOverride"] = "2030-01-01T00:00:00Z"
			b, e := CanonicalJSON(x)
			if e != nil {
				t.Fatal(e)
			}
			p.Records["plan"] = b
		},
		"missing-record": func(p *Packet) { delete(p.Records, "projection-36-PC4") },
	} {
		t.Run(name, func(t *testing.T) {
			p := clonePacket(f.packet)
			mutate(&p)
			if _, e = v.Verify(p); e == nil {
				t.Fatal("foreign/partial packet accepted")
			}
		})
	}
}
