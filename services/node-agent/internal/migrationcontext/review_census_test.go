package migrationcontext

import (
	"bytes"
	"strings"
	"testing"
)

func TestReviewR5AllBridgeObjectsAndMethodSets(t *testing.T) {
	root := repository(t)
	paths := exports(t, root)
	original := sourceSet(t, root, k1Base)
	base, e := packageCensus(original, paths)
	if e != nil {
		t.Fatal(e)
	}
	ids, e := actualBridgeObjects(paths)
	if e != nil {
		t.Fatal(e)
	}
	t.Logf("actual resolved bridge objects: %v", ids)
	for _, m := range []struct{ name, file, marker, before, after string }{
		{"Packet-named-map", "verify.go", "type Packet struct {", "type ReviewProbe map[string]string", "type ReviewProbe map[string]any"},
		{"Report-named-slice", "verify.go", "type Report struct {", "type ReviewProbe []string", "type ReviewProbe []any"},
	} {
		t.Run(m.name, func(t *testing.T) {
			before := copyMap(original)
			raw := string(before[m.file])
			if !strings.Contains(raw, m.marker) {
				t.Fatal("missing actual type target")
			}
			before[m.file] = []byte(strings.Replace(raw, m.marker, m.marker+"\n ReviewProbe ReviewProbe", 1) + "\n" + m.before)
			a, e := packageCensus(before, paths)
			if e != nil {
				t.Fatal("control must fully typecheck", e)
			}
			after := copyMap(before)
			after[m.file] = bytes.Replace(after[m.file], []byte(m.before), []byte(m.after), 1)
			b, e := packageCensus(after, paths)
			if e != nil {
				t.Fatal("mutant must fully typecheck", e)
			}
			if a.shape == b.shape {
				t.Fatal("non-constructor bridge shape escaped simulated raw repin")
			}
		})
	}
	t.Run("CanonicalJSON-variadic", func(t *testing.T) {
		src := copyMap(original)
		old := []byte("func CanonicalJSON(v any)")
		if !bytes.Contains(src["json.go"], old) {
			t.Fatal("actual function target absent")
		}
		src["json.go"] = bytes.Replace(src["json.go"], old, []byte("func CanonicalJSON(v any, opts ...any)"), 1)
		c, e := packageCensus(src, paths)
		if e != nil {
			t.Fatal("variadic mutant must typecheck", e)
		}
		if c.shape == base.shape {
			t.Fatal("variadic signature escaped")
		}
	})
	for _, receiver := range []string{"InstalledTrust", "*InstalledTrust"} {
		t.Run("MarshalJSON-"+receiver, func(t *testing.T) {
			src := copyMap(original)
			src["review_method.go"] = []byte("package migrationverify\nfunc (" + receiver + ") MarshalJSON() ([]byte,error) { return []byte(`{}`),nil }\n")
			c, e := packageCensus(src, paths)
			if e != nil {
				t.Fatal("method mutant must typecheck", e)
			}
			if c.shape == base.shape {
				t.Fatal("named/pointer method addition escaped")
			}
		})
	}
	t.Run("method-declaration-order-control", func(t *testing.T) {
		src := copyMap(original)
		a := "func (InstalledTrust) ReviewA() string {return \"a\"}\n"
		z := "func (*InstalledTrust) ReviewZ() string {return \"z\"}\n"
		src["review_method.go"] = []byte("package migrationverify\n" + z + a)
		first, e := packageCensus(src, paths)
		if e != nil {
			t.Fatal(e)
		}
		src["review_method.go"] = []byte("package migrationverify\n" + a + z)
		second, e := packageCensus(src, paths)
		if e != nil {
			t.Fatal(e)
		}
		if first.shape != second.shape {
			t.Fatal("method set is not canonical/sorted")
		}
	})
}
