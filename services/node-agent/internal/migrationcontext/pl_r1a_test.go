package migrationcontext

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// Compile actual public bodies with each mutant; never execute those bodies.
// A build failure is NOT proof that the source boundary refused an effect.
func buildPLMutation(t *testing.T, root string, src map[string][]byte) {
	t.Helper()
	dir := t.TempDir()
	own := filepath.Join(dir, "internal/migrationcontext")
	if e := os.MkdirAll(own, 0700); e != nil {
		t.Fatal(e)
	}
	for n, b := range src {
		if filepath.Ext(n) == ".go" && !strings.HasSuffix(n, "_test.go") {
			if e := os.WriteFile(filepath.Join(own, n), b, 0600); e != nil {
				t.Fatal(e)
			}
		}
	}
	for _, name := range []string{"go.mod", "go.sum"} {
		b, e := os.ReadFile(filepath.Join(root, "services/node-agent", name))
		if e != nil {
			t.Fatal(e)
		}
		if name == "go.mod" {
			b = []byte(strings.Replace(string(b), "../../packages/contracts-go", filepath.ToSlash(filepath.Join(root, "packages/contracts-go")), 1))
		}
		if e = os.WriteFile(filepath.Join(dir, name), b, 0600); e != nil {
			t.Fatal(e)
		}
	}
	base := filepath.Join(root, filepath.FromSlash(k1Dir))
	e := filepath.WalkDir(base, func(path string, d os.DirEntry, e error) error {
		if e != nil {
			return e
		}
		if d.IsDir() {
			return nil
		}
		rel, e := filepath.Rel(base, path)
		if e != nil {
			return e
		}
		if d.Type()&os.ModeSymlink != 0 {
			return os.ErrInvalid
		}
		if !(strings.HasPrefix(filepath.ToSlash(rel), "resources/") || strings.HasSuffix(rel, ".go") && !strings.HasSuffix(rel, "_test.go")) {
			return nil
		}
		out := filepath.Join(dir, "migrationverify", rel)
		if e = os.MkdirAll(filepath.Dir(out), 0700); e != nil {
			return e
		}
		b, e := os.ReadFile(path)
		if e != nil {
			return e
		}
		return os.WriteFile(out, b, 0600)
	})
	if e != nil {
		t.Fatal(e)
	}
	sourceCommand(t, dir, "go", "build", "-p=1", "./internal/migrationcontext")
	t.Log("actual go build -p=1 ./internal/migrationcontext exit0; mutant body NOT executed")
}

func TestPLR1AActualBuildsThenBoundaryRefuses(t *testing.T) {
	root := repository(t)
	original := ownProductionSources(t, root)
	paths := exports(t, root)
	control, e := checkSourcePackage(ownImport, original, paths, nil)
	if e != nil {
		t.Fatal(e)
	}
	if e = sourceEffects(original, control); e != nil {
		t.Fatal("actual pure source must pass", e)
	}
	cases := []struct {
		name, code string
		refuse     bool
	}{
		{"own-interface-Certificate-Verify", `import "crypto/x509"
type Probe interface{ Verify(x509.VerifyOptions) ([][]*x509.Certificate,error) }
func probe(c *x509.Certificate){var v Probe=c;_,_=v.Verify(x509.VerifyOptions{})}`, true},
		{"generic-constraint-Certificate-Verify", `import "crypto/x509"
func probe[T interface{Verify(x509.VerifyOptions)([][]*x509.Certificate,error)}](c T){_,_=c.Verify(x509.VerifyOptions{})}
func use(c *x509.Certificate){probe(c)}`, true},
		{"instantiated-generic-interface", `import "crypto/x509"
type Probe[T any] interface{Verify(T)([][]*x509.Certificate,error)}
func probe(c *x509.Certificate){var v Probe[x509.VerifyOptions]=c;_,_=v.Verify(x509.VerifyOptions{})}`, true},
		{"own-interface-Time-Local", `import clock "time"
type Probe interface{Local()clock.Time}
func probe(){var v Probe=clock.Time{};_=v.Local()}`, true},
		{"pointer-write-foreign-Local", `import clock "time"
func probe(){p:=&clock.Local;*p=clock.UTC}`, true},
		{"pointer-address-allowed-read-UTC", `import clock "time"
func probe(){p:=&clock.UTC;*p=clock.UTC}`, true},
		{"dot-import-foreign-Local-read", `import . "time"
func probe(){_=Local}`, true},
		{"dot-import-UTC-write", `import . "time"
func probe(){UTC=nil}`, true},
		{"selector-UTC-write-control", `import clock "time"
func probe(){clock.UTC=nil}`, true},
		{"foreign-interface-alias-transitive-embed", `import "io"
type Alias=io.Reader
type Level interface{Alias}
type Probe interface{Level;read()string}`, true},
		{"interface-method-value-control", `import "crypto/x509"
type Probe interface{Verify(x509.VerifyOptions)([][]*x509.Certificate,error)}
func probe(c *x509.Certificate){var v Probe=c;f:=v.Verify;_,_=f(x509.VerifyOptions{})}`, true},
		{"embedded-concrete-promotion-control", `import "crypto/x509"
type Probe struct{*x509.Certificate}
func probe(c *x509.Certificate){_,_=Probe{c}.Verify(x509.VerifyOptions{})}`, true},
		{"dot-import-clock-control", `import . "time"
func probe(){_=Now()}`, true},
		{"package-function-value-control", `import "time"
var probe=time.Now`, true},
		{"defer-clock-control", `import "time"
func probe(){defer time.Since(time.Time{})}`, true},
		{"closure-value-control", `func probe(){f:=func(){};f()}`, true},
		{"unexported-own-interface-UTC-positive", `import clock "time"
type Probe interface{read()string}
func probe(p Probe)string{_=clock.UTC;return p.read()}`, false},
		{"unexported-generic-constraint-positive", `type Probe interface{read()string}
type Value struct{}
func(Value)read()string{return "pure"}
func probe[T Probe](p T)string{return p.read()}
func use(){_=probe(Value{})}`, false},
	}
	for _, m := range cases {
		t.Run(m.name, func(t *testing.T) {
			src := copyMap(original)
			src["pl_probe.go"] = []byte("package migrationcontext\n" + m.code)
			buildPLMutation(t, root, src)
			checked, e := checkSourcePackage(ownImport, src, paths, nil)
			if e != nil {
				t.Fatal("actual built source must typecheck", e)
			}
			e = sourceEffects(src, checked)
			if (e != nil) != m.refuse {
				t.Fatalf("want refusal=%t, got %v", m.refuse, e)
			}
			t.Logf("resolved gate refused=%t after actual build exit0", e != nil)
		})
	}
}
