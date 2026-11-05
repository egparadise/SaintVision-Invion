package migrationverify

import (
	"encoding/json"
	"testing"
	"time"
)

func shapeRecipeVerifier(t *testing.T) (*Verifier, map[string]any, map[string]string) {
	t.Helper()
	g, inputs, p, k := originalGraph(t)
	d, e := g.check(inputs, p, k)
	if e != nil {
		t.Fatal(e)
	}
	cs, e := loadContracts()
	if e != nil {
		t.Fatal(e)
	}
	i := inputs.(map[string]any)
	facts := i["facts"].(map[string]any)
	outcomes := map[string]any{}
	slots := map[string]any{}
	for id, x := range p {
		if k[id] != "migration-event" {
			continue
		}
		b := x.(map[string]any)["body"].(map[string]any)
		seq := string(b["sequence"].(json.Number))
		outcome := "known-success"
		if b["recordKind"] == "failure" {
			outcome = "unknown"
		}
		outcomes[b["operationId"].(string)+"|"+seq] = outcome
		slots[id] = b["targetSlot"]
	}
	facts["effectOutcomes"] = outcomes
	facts["eventSlots"] = slots
	plan := p["plan"].(map[string]any)["body"].(map[string]any)
	members := []MemberIdentity{}
	for _, x := range plan["memberInputs"].([]any) {
		m := x.(map[string]any)
		members = append(members, MemberIdentity{Slot: m["slot"].(string), Scope: m["scope"]})
	}
	v := &Verifier{contracts: cs, graph: g, trust: InstalledTrust{Members: members, CohortID: facts["cohortId"].(string), NodeKinds: k}, ctx: TrustedContext{SemanticInputs: inputs, Now: time.Date(2030, 1, 1, 0, 0, 0, 0, time.UTC), MigrationOperationID: facts["migrationOperationId"].(string)}}
	return v, p, d
}

func TestAll112OriginalSubjectsAndScopedPolicyAreDerived(t *testing.T) {
	v, p, d := shapeRecipeVerifier(t)
	coverage := fixture(t, "reference-graph-coverage.json").(map[string]any)["structuredProofReferences"].([]any)
	wantScopes := map[string]string{}
	for _, x := range coverage {
		x := x.(map[string]any)
		wantScopes[x["node"].(string)+x["pointer"].(string)] = x["scope"].(string)
	}
	count := 0
	seen := map[string]bool{}
	for id, payload := range p {
		if e := visitProofs(id, v.trust.NodeKinds[id], payload, func(loc proofLocation) error {
			s, e := v.slot(loc, payload)
			if e != nil {
				return e
			}
			c := v.contracts.byID[s.ContractID]
			sub, _, e := v.subject(loc, p, d, c)
			if e != nil {
				return e
			}
			if !equal(sub, loc.reference["typedSubject"]) {
				t.Errorf("derived subject mismatch %s%s\ngot %v\nwant %v", id, loc.path, sub, loc.reference["typedSubject"])
			}
			a, e := v.proofAuthority(loc, sub)
			if e != nil {
				return e
			}
			scope := wantScopes[id+loc.path]
			var want any
			switch {
			case scope == "COHORT":
				want = v.cohortAuthority()
			case scope == "PC2" || scope == "PC4":
				m, e := v.member(scope)
				if e != nil {
					return e
				}
				want = nodeAuthority(m.Scope)
			default:
				want = componentAuthority(scope[len("CODE:"):])
			}
			if !equal(a, want) {
				t.Errorf("wrong role authority %s%s", id, loc.path)
			}
			seen[s.SlotID] = true
			count++
			return nil
		}); e != nil {
			t.Fatalf("%s: %v", id, e)
		}
	}
	if count != 112 || len(seen) != 75 {
		t.Fatalf("proofs=%d populated slots=%d", count, len(seen))
	}
}

func TestArgvSeparateFromC2AndProcessBytes(t *testing.T) {
	a := []any{"<>&\u2028\u2029한", `\u2028`, "x\n"}
	raw, e := CanonicalArgvJSON(a)
	if e != nil {
		t.Fatal(e)
	}
	want := "[\"<>&\u2028\u2029한\",\"\\\\u2028\",\"x\\n\"]"
	if string(raw) != want {
		t.Fatalf("%q != %q", raw, want)
	}
	c2, e := CanonicalJSON(a)
	if e != nil {
		t.Fatal(e)
	}
	if string(c2) == string(raw) {
		t.Fatal("argv/C2 collapsed")
	}
	if _, e := CanonicalArgvJSON([]any{"bad\x00arg"}); e == nil {
		t.Fatal("NUL argv")
	}
}
