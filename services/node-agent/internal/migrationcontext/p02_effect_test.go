package migrationcontext

import (
	"strings"
	"testing"
)

func TestP02InternalPureEpochExactObjectBoundary(t *testing.T) {
	root := repository(t)
	original := ownProductionSources(t, root)
	paths := exports(t, root)
	cases := []struct {
		name, code string
		allowed    bool
		cause      string
	}{
		{"import-alias-Unix-UTC", `import clock "time";func p02probe(){_ = clock.Unix(1,0).UTC()}`, true, ""},
		{"type-alias-UTC", `import clock "time";type p02alias=clock.Time;func p02probe(){_ = (p02alias{}).UTC()}`, true, ""},
		{"method-expression-UTC", `import clock "time";func p02probe(){_ = clock.Time.UTC(clock.Unix(1,0))}`, true, ""},
		{"ambient-now", `import clock "time";func p02probe(){_ = clock.Now()}`, false, "time.Now"},
		{"ambient-since", `import clock "time";func p02probe(){_ = clock.Since(clock.Time{})}`, false, "time.Since"},
		{"timer", `import clock "time";func p02probe(){_ = clock.NewTimer(1)}`, false, "time.NewTimer"},
		{"ungranted-neighbor", `import clock "time";func p02probe(){_ = (clock.Time{}).Local()}`, false, "time.Time.Local"},
		{"signing", `import ed "crypto/ed25519";func p02probe(){_ = ed.Sign(nil,nil)}`, false, "crypto/ed25519.Sign"},
		{"foreign-var-write", `import clock "time";func p02probe(){clock.UTC=nil}`, false, "foreign state write"},
		{"foreign-pointee-write", `import clock "time";func p02probe(p *clock.Time){*p=clock.Time{}}`, false, "foreign pointee write"},
	}
	for _, x := range cases {
		t.Run(x.name, func(t *testing.T) {
			src := copyMap(original)
			src["p02probe.go"] = []byte("package migrationcontext\n" + x.code)
			checked, e := checkSourcePackage(ownImport, src, paths, nil)
			if e != nil {
				t.Fatal("compile-valid resolved-object test required", e)
			}
			e = sourceEffects(src, checked)
			if x.allowed {
				if e != nil {
					t.Fatal("exact pure object control", e)
				}
			} else {
				if e == nil || !strings.Contains(e.Error(), x.cause) {
					t.Fatal("wrong causal denial", x.cause, e)
				}
			}
		})
	}
}
