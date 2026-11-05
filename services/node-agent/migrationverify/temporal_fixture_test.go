package migrationverify

// Only ephemeral TEST records/graph are retimed. The pinned source archive and
// original dummy inputs remain byte-exact. No trusted Now is backdated.
import (
	"os"
	"testing"
	"time"
)

func durableFixtureTimeline(t *testing.T, v *Verifier, p map[string]any, original map[string]string, overrides map[string]int64) ([]byte, map[string]time.Time) {
	t.Helper()
	base := v.ctx.Now
	times := map[string]time.Time{}
	seconds := func(seq int64) int64 {
		if seq == 35 {
			return 610
		}
		if seq == 36 {
			return 620
		}
		return seq * 2
	}
	for id, kind := range v.trust.NodeKinds {
		var sec int64
		b, _ := object(p[id])
		if body, ok := b["body"]; ok {
			b, _ = object(body)
		}
		switch kind {
		case "migration-event":
			n, _ := number64(b["sequence"])
			sec = seconds(n)
		case "runtime-inventory":
			sec = 54
		case "terminal-seal":
			if b["slot"] == "PC2" {
				sec = 59
			} else {
				sec = 63
			}
		case "operation-lease":
			if b["mode"] == "RELEASED" {
				sec = 68
			} else if id == "lease-restore" {
				sec = 600
			}
		case "migration-journal":
			latest, _ := object(b["latestEvent"])
			n, _ := number64(latest["sequence"])
			sec = seconds(n)
		case "api-request":
			var earliest int64
			for eid, ep := range p {
				if v.trust.NodeKinds[eid] != "migration-event" {
					continue
				}
				eb, _ := pointer(ep, "/body")
				em, _ := object(eb)
				if em["requestSHA256"] == original[id] {
					n, _ := number64(em["sequence"])
					if earliest == 0 || n < earliest {
						earliest = n
					}
				}
			}
			if earliest == 0 {
				t.Fatal("missing TEST request event", id)
			}
			sec = seconds(earliest)
		}
		times[id] = base.Add(time.Duration(sec) * time.Second)
	}
	for id, sec := range overrides {
		times[id] = base.Add(time.Duration(sec) * time.Second)
	}
	inputs := v.ctx.SemanticInputs.(map[string]any)
	inputs["plan"].(map[string]any)["expiresAt"] = base.Add(1800 * time.Second).Format(time.RFC3339)
	raw, e := os.ReadFile("testdata/artifact-reference-graph.json")
	if e != nil {
		t.Fatal(e)
	}
	value, e := ParseJSON(raw)
	if e != nil {
		t.Fatal(e)
	}
	for _, value := range value.(map[string]any)["rules"].([]any) {
		r := value.(map[string]any)
		id := r["node"].(string)
		path := r["pointer"].(string)
		var at time.Time
		switch path {
		case "/body/recordedAt", "/body/publishedAt", "/body/sealedAt":
			at = times[id]
		case "/body/acquiredAt":
			if id == "lease-restore" {
				at = base.Add(600 * time.Second)
			} else {
				at = base
			}
		case "/body/expiresAt":
			if v.trust.NodeKinds[id] == "operation-lease" {
				if id == "lease-restore" {
					at = base.Add(1200 * time.Second)
				} else {
					at = base.Add(300 * time.Second)
				}
			}
		}
		if !at.IsZero() {
			stamp := at.Format(time.RFC3339)
			r["expression"] = map[string]any{"const": stamp}
			setPointer(t, p[id], path, stamp)
		}
	}
	raw, e = CanonicalJSON(value)
	if e != nil {
		t.Fatal(e)
	}
	v.graph, e = compileGraph(raw, v.trust.NodeKinds)
	if e != nil {
		t.Fatal(e)
	}
	v.ctx.Now = base.Add(630 * time.Second)
	return raw, times
}

func TestDurableTwoEpochHistoryAndCurrent(t *testing.T) {
	f := newCryptoFixtureMutated(t, nil, cryptoFixtureOptions{DurableHistory: true})
	old := f.context.History.Operations[f.context.MigrationOperationID]
	if !f.context.Now.After(old.ExpiresAt) || f.context.Operations[f.context.MigrationOperationID].OperationID != "" {
		t.Fatal("not an expired historical-only epoch1")
	}
	v, e := NewVerifier(f.installed, f.context)
	if e != nil {
		t.Fatal(e)
	}
	if _, e = v.Verify(f.packet); e != nil {
		t.Fatal("durable history rejected:", e)
	}
	if _, e = v.VerifyCurrentProjectionSet(f.packet, "cohort-36"); e != nil {
		t.Fatal("latest epoch2 current rejected:", e)
	}
	t.Log("TEST timeline: epoch1 HELD 0..300, release68; epoch2 HELD600..1200, events610/620, Now630; original Node proofs32/52; separate current proofs630")
}
