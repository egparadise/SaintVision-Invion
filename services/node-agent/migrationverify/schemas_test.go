package migrationverify

import (
	"encoding/hex"
	"os"
	"testing"
)

func fixture(t *testing.T, name string) any {
	t.Helper()
	b, e := os.ReadFile("testdata/" + name)
	if e != nil {
		t.Fatal(e)
	}
	v, e := ParseJSON(b)
	if e != nil {
		t.Fatal(e)
	}
	return v
}

func TestExactOfflineClosureAndOriginalShapeOnly(t *testing.T) {
	s, e := LoadSchemas()
	if e != nil {
		t.Fatal(e)
	}
	nodes := fixture(t, "scenario-objects.json").(map[string]any)["nodes"].(map[string]any)
	if len(nodes) != 195 {
		t.Fatal(len(nodes))
	}
	for id, x := range nodes {
		n := x.(map[string]any)
		kind := n["kind"].(string)
		if e := s.Validate(kind, n["payload"]); e != nil {
			t.Fatalf("%s: %v", id, e)
		}
		d, e := ArtifactDigest(kind, n["payload"])
		if e != nil {
			t.Fatal(e)
		}
		if d != n["sha256"] {
			t.Fatalf("%s byte digest differs", id)
		}
	}
	// This test establishes structural/byte equivalence only. Original signatures
	// are dummy identifiers; successful schema validation grants no authority.
}

func TestDerivedByteVectors(t *testing.T) {
	v := fixture(t, "derived-byte-ordering-vectors.json").(map[string]any)
	for _, x := range v["positive"].([]any) {
		x := x.(map[string]any)
		b, e := CanonicalJSON(x["body"])
		if e != nil {
			t.Fatal(e)
		}
		if hex.EncodeToString(b) != x["canonicalBodyHex"] {
			t.Fatal("canonical body mismatch")
		}
		d, e := ArtifactDigest("cohort-projection-set", x["body"])
		if e != nil {
			t.Fatal(e)
		}
		if d != x["derivedDigestSHA256"] {
			t.Fatalf("vector %v digest mismatch", x["id"])
		}
	}
}

func TestOfflineLoaderNeverResolves(t *testing.T) {
	if _, e := (noResolution{}).Load("https://example.invalid/schema"); e == nil {
		t.Fatal("network fallback")
	}
}
