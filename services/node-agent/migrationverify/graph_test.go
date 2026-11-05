package migrationverify

import (
	"encoding/json"
	"os"
	"testing"
)

func originalGraph(t *testing.T) (*graph, any, map[string]any, map[string]string) {
	t.Helper()
	raw, e := os.ReadFile("testdata/artifact-reference-graph.json")
	if e != nil {
		t.Fatal(e)
	}
	ns := fixture(t, "scenario-objects.json").(map[string]any)["nodes"].(map[string]any)
	kinds := map[string]string{}
	payloads := map[string]any{}
	for id, x := range ns {
		n := x.(map[string]any)
		kinds[id] = n["kind"].(string)
		payloads[id] = n["payload"]
	}
	g, e := compileGraph(raw, kinds)
	if e != nil {
		t.Fatal(e)
	}
	return g, fixture(t, "scenario-inputs.json"), payloads, kinds
}

func TestCompleteGraphDependencyOrderAndCoverage(t *testing.T) {
	g, in, p, k := originalGraph(t)
	d, e := g.check(in, p, k)
	if e != nil {
		t.Fatal(e)
	}
	if len(d) != 195 {
		t.Fatal(len(d))
	}
	count := 0
	for _, rr := range g.rules {
		count += len(rr)
	}
	if count != 3469 {
		t.Fatal(count)
	}
	// The first response's set is later in the rule list, so this positive is
	// sensitive to mistakenly treating list order as dependency order.
	index := map[string]int{}
	for i, id := range g.order {
		index[id] = i
	}
	if index["cohort-01"] >= index["response-request-01-inspectAndValidate"] {
		t.Fatal("forward dependency not resolved")
	}
	bad := copyJSON(p["cohort-36"]).(map[string]any)
	bad["fenceEpoch"] = json.Number("1")
	p["cohort-36"] = bad
	if _, e = g.check(in, p, k); e == nil {
		t.Fatal("restore epoch2 confused with released epoch1")
	}
}

func TestGraphRejectsMissingDuplicateCycleAndUnknown(t *testing.T) {
	for _, rules := range []string{
		`[{"node":"a","pointer":"/x","expression":{"digest":"missing"}}]`,
		`[{"node":"a","pointer":"/x","expression":{"digest":"a"}}]`,
		`[{"node":"a","pointer":"/x","expression":{"const":1}},{"node":"a","pointer":"/x","expression":{"const":1}}]`,
		`[{"node":"a","pointer":"/x","expression":{"unknown":1}}]`,
	} {
		if _, e := compileGraph([]byte(`{"rules":`+rules+`}`), map[string]string{"a": "api-request"}); e == nil {
			t.Fatal(rules)
		}
	}
	g, e := compileGraph([]byte(`{"rules":[{"node":"a","pointer":"/x","expression":{"const":1}}]}`), map[string]string{"a": "api-request"})
	if e != nil {
		t.Fatal(e)
	}
	if _, e = g.check(nil, map[string]any{"a": map[string]any{"x": json.Number("1"), "uncovered": true}}, map[string]string{"a": "api-request"}); e == nil {
		t.Fatal("uncovered leaf")
	}
}
