package migrationcontext

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// PL-I3: a stale pin, build/type error, or unrelated refusal cannot substitute
// for the intended source-boundary reason. Alias traversal can reach the same
// forbidden foreign interface via either its named embed or its method set.
var plR1AReasons = map[string][]string{
	"own-interface-Certificate-Verify":         {"interface/constraint method must be unexported own object:"},
	"generic-constraint-Certificate-Verify":    {"interface/constraint method must be unexported own object:"},
	"instantiated-generic-interface":           {"interface/constraint method must be unexported own object:"},
	"own-interface-Time-Local":                 {"interface/constraint method must be unexported own object:"},
	"pointer-write-foreign-Local":              {"foreign package variable read forbidden: time.Local"},
	"pointer-address-allowed-read-UTC":         {"foreign package variable address forbidden: time.UTC"},
	"dot-import-foreign-Local-read":            {"foreign package variable read forbidden: time.Local"},
	"dot-import-UTC-write":                     {"foreign state write forbidden: time.UTC"},
	"selector-UTC-write-control":               {"foreign state write forbidden: time.UTC"},
	"foreign-interface-alias-transitive-embed": {"foreign embedded interface forbidden: io.Reader", "interface/constraint method must be unexported own object: io.Read"},
	"interface-method-value-control":           {"interface/constraint method must be unexported own object:"},
	"embedded-concrete-promotion-control":      {"unreviewed function/method object: crypto/x509.Certificate.Verify"},
	"dot-import-clock-control":                 {"unreviewed function/method object: time.Now"},
	"package-function-value-control":           {"unreviewed function/method object: time.Now"},
	"defer-clock-control":                      {"unreviewed function/method object: time.Since"},
	"closure-value-control":                    {"unresolved/function-value/callback call forbidden"},
}

func assertPLReason(t *testing.T, name string, refuse bool, prefixes []string, e error) {
	t.Helper()
	reason := "<nil>"
	if e != nil {
		reason = e.Error()
	}
	t.Logf("REASON case=%s build=0 typecheck=0 refused=%t reason=%s", name, e != nil, reason)
	if !refuse {
		if e != nil {
			t.Fatalf("positive control refused: %s", reason)
		}
		return
	}
	if len(prefixes) == 0 {
		t.Fatal("negative case has no intended refusal-reason contract")
	}
	for _, prefix := range prefixes {
		if e != nil && strings.HasPrefix(reason, prefix) {
			return
		}
	}
	t.Fatalf("want intended refusal prefixes=%q, got=%s", prefixes, reason)
}

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
			assertPLReason(t, m.name, m.refuse, plR1AReasons[m.name], e)
		})
	}
}

func TestPLR1BCompiledWriteTargetsAndReasons(t *testing.T) {
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
	cases := []struct{ name, code, reason string }{
		// The seven exact compile-valid reviewer escapes; no body executes.
		{"E1-range-UTC", `import clock "time"
func probe(){for _, clock.UTC = range []*clock.Location{nil} {}}`, "foreign state write forbidden: time.UTC"},
		{"range-dot-UTC", `import . "time"
func probe(){for _, UTC = range []*Location{nil} {}}`, "foreign state write forbidden: time.UTC"},
		{"E2-deref-UTC", `import clock "time"
func probe(){*clock.UTC = clock.Location{}}`, "foreign pointee write forbidden: time.Location"},
		{"deref-local-pointer-copy", `import clock "time"
func probe(){p:=clock.UTC;*p=clock.Location{}}`, "foreign pointee write forbidden: time.Location"},
		{"E3-deref-pure-Location", `import clock "time"
func probe(){*clock.Time{}.Location() = clock.Location{}}`, "foreign pointee write forbidden: time.Location"},
		{"deref-helper-parameter", `import clock "time"
func set(l *clock.Location){*l=clock.Location{}}
func probe(){set(clock.Time{}.Location())}`, "foreign pointee write forbidden: time.Location"},
		{"range-deref-UTC", `import clock "time"
func probe(){for _, *clock.UTC = range []clock.Location{{}} {}}`, "foreign pointee write forbidden: time.Location"},
		// Complete write forms and roots, including implicit/promoted dereference.
		{"paren-direct-UTC", `import clock "time"
func probe(){(clock.UTC)=nil}`, "foreign state write forbidden: time.UTC"},
		{"tuple-direct-UTC", `import clock "time"
func probe(){x:=0;clock.UTC,x=nil,1;_=x}`, "foreign state write forbidden: time.UTC"},
		{"select-direct-UTC", `import clock "time"
func probe(ch chan *clock.Location){select{case clock.UTC = <-ch:}}`, "foreign state write forbidden: time.UTC"},
		{"foreign-pointee-alias", `import clock "time"
type Alias=clock.Location
func probe(p *Alias){*p=Alias{}}`, "foreign pointee write forbidden: time.Location"},
		{"defined-pointer-to-foreign-pointee", `import clock "time"
type Pointer *clock.Location
func probe(p Pointer){*p=clock.Location{}}`, "foreign pointee write forbidden: time.Location"},
		{"index-local-pointer-container", `import clock "time"
func probe(){ps:=[]*clock.Location{clock.UTC};*(ps[0])=clock.Location{}}`, "foreign pointee write forbidden: time.Location"},
		{"paren-deref-UTC", `import clock "time"
func probe(){(*((clock.UTC)))=clock.Location{}}`, "foreign pointee write forbidden: time.Location"},
		{"tuple-deref-UTC", `import clock "time"
func probe(){x:=0;*clock.UTC,x=clock.Location{},1;_=x}`, "foreign pointee write forbidden: time.Location"},
		{"select-deref-UTC", `import clock "time"
func probe(ch chan clock.Location){select{case *clock.UTC = <-ch:}}`, "foreign pointee write forbidden: time.Location"},
		{"implicit-selector-foreign-pointer", `import "crypto/x509"
func probe(c *x509.Certificate){c.SerialNumber=nil}`, "foreign pointee write forbidden: crypto/x509.Certificate"},
		{"explicit-selector-foreign-pointer", `import "crypto/x509"
func probe(c *x509.Certificate){(*c).SerialNumber=nil}`, "foreign pointee write forbidden: crypto/x509.Certificate"},
		{"own-root-foreign-pointer-field", `import "crypto/x509"
type owned struct{cert *x509.Certificate}
func probe(v *owned){v.cert.SerialNumber=nil}`, "foreign pointee write forbidden: crypto/x509.Certificate"},
		{"promoted-foreign-pointer-field", `import "crypto/x509"
type owned struct{*x509.Certificate}
func probe(v owned){v.Version++}`, "foreign pointee write forbidden: crypto/x509.Certificate"},
		{"compound-foreign-selector", `import "crypto/x509"
func probe(c *x509.Certificate){c.Version+=1}`, "foreign pointee write forbidden: crypto/x509.Certificate"},
		{"incdec-foreign-selector", `import "crypto/x509"
func probe(c *x509.Certificate){c.Version++}`, "foreign pointee write forbidden: crypto/x509.Certificate"},
		{"range-key-foreign-selector", `import "crypto/x509"
func probe(c *x509.Certificate){for c.Version = range []int{1} {}}`, "foreign pointee write forbidden: crypto/x509.Certificate"},
		{"index-base-foreign-pointer", `import "crypto/x509"
func probe(cs []*x509.Certificate){cs[0].Version++}`, "foreign pointee write forbidden: crypto/x509.Certificate"},
		{"unnamed-array-pointer-conservative", `type Alias=[1]int
func probe(p *Alias){p[0]=1}`, "foreign pointee write forbidden: [1]int"},
		{"slice-root-foreign-pointee", `import ed "crypto/ed25519"
func probe(p *ed.PrivateKey){(*p)[:][0]++}`, "foreign pointee write forbidden: crypto/ed25519.PrivateKey"},
		// Positive controls: the restriction is pointee TYPE-based, not alias analysis.
		{"UTC-pure-compare", `import clock "time"
func probe()bool{return clock.Time{}.Location()==clock.UTC}`, ""},
		{"own-var-range-assignment", `var own int
func probe(){for _,own=range []int{1} {}}`, ""},
		{"local-var-range-assignment", `func probe(){var v int;for _,v=range []int{1} {};_=v}`, ""},
		{"local-range-definition", `func probe(){for _,v:=range []int{1} {_=v}}`, ""},
		{"own-pointer-local-mutation", `type owned struct{N int;Data []int}
func probe(){p:=&owned{};p.N=1;p.N++;*p=owned{};p.Data=[]int{1};p.Data[0]++}`, ""},
		{"own-array-pointer-index", `type owned [1]int
func probe(p *owned){p[0]++;p[0]=1}`, ""},
		{"own-scalar-pointer-incdec", `type owned int
func probe(p *owned){(*p)++}`, ""},
		{"own-alias-pointer", `type owned struct{N int}
type Alias=owned
func probe(p *Alias){p.N++}`, ""},
		{"local-foreign-value-copy", `import "crypto/x509"
func probe(){c:=x509.Certificate{};c.Version++;c.SerialNumber=nil}`, ""},
		{"slice-root-local-value", `func probe(){v:=[]int{1};v[:][0]++}`, ""},
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
			assertPLReason(t, m.name, m.reason != "", []string{m.reason}, e)
		})
	}
}

// New owner-run PL-R1c cases; actual independent delta review is pending.
func TestPLR1CCompiledPointerConversionsAndControls(t *testing.T) {
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
	// Owner adaptation of actual 5a3c reviewer probes: empty want accepts a
	// declared storage limit or positive control; N1-N6 require conversion refusal.
	// otherwise the intended refusal prefix.
	cases := []struct{ name, kind, code, want string }{
		// Conversion laundering: foreign pointee re-typed as own named type.
		{"N1-conv-UTC-package-type", "CONVERSION_NEGATIVE", `import clock "time"
type plLaunder clock.Location
func probe(){*(*plLaunder)(clock.UTC)=plLaunder{}}`, "pointee-changing pointer conversion forbidden:"},
		{"N2-conv-UTC-local-type-alias-var", "CONVERSION_NEGATIVE", `import clock "time"
func probe(){type L clock.Location;p:=(*L)(clock.UTC);*p=L{}}`, "pointee-changing pointer conversion forbidden:"},
		{"N3-conv-Location-own-method", "CONVERSION_NEGATIVE", `import clock "time"
type L clock.Location
func (l *L) reset(){*l=L{}}
func probe(){(*L)(clock.Time{}.Location()).reset()}`, "pointee-changing pointer conversion forbidden:"},
		{"N4-conv-Certificate-field", "CONVERSION_NEGATIVE", `import "crypto/x509"
type C x509.Certificate
func probe(c *x509.Certificate){(*C)(c).Version++}`, "pointee-changing pointer conversion forbidden:"},
		{"N5-conv-foreign-field-address", "CONVERSION_NEGATIVE", `import "crypto/x509"
type n int
func probe(c *x509.Certificate){*(*n)(&c.Version)=1}`, "pointee-changing pointer conversion forbidden:"},
		{"N6-slice-to-own-array-pointer", "CONVERSION_NEGATIVE", `import ed "crypto/ed25519"
type a [64]byte
func probe(k ed.PrivateKey){(*a)(k)[0]++}`, "pointee-changing pointer conversion forbidden:"},
		// Reference-typed storage: declared provenance limit (not pointees).
		{"S1-slice-local-copy-of-pointee", "LIMIT", `import ed "crypto/ed25519"
func probe(p *ed.PrivateKey){k:=*p;k[0]++}`, ""},
		{"S2-slice-parameter", "LIMIT", `import ed "crypto/ed25519"
func probe(k ed.PrivateKey){k[0]++}`, ""},
		// Independent refusals the 484 gate must keep.
		{"R1-double-deref-local", "REFUSE", `import clock "time"
func probe(){p:=clock.UTC;q:=&p;**q=clock.Location{}}`, "foreign pointee write forbidden: time.Location"},
		{"R2-type-assert-deref", "REFUSE", `import clock "time"
func probe(v any){*v.(*clock.Location)=clock.Location{}}`, "foreign pointee write forbidden: time.Location"},
		{"R3-generic-helper-typeparam", "REFUSE", `import clock "time"
func set[T any](p *T,v T){*p=v}
func probe(){set(clock.UTC,clock.Location{})}`, "foreign pointee write forbidden: T"},
		{"R4-foreign-field-address-builtin", "REFUSE", `import "crypto/x509"
func probe(c *x509.Certificate){p:=&c.Version;*p=1}`, "foreign pointee write forbidden: int"},
		{"R5-uncalled-closure-deref", "REFUSE", `import clock "time"
func probe(){f:=func(){*clock.UTC=clock.Location{}};_=f}`, "foreign pointee write forbidden: time.Location"},
		{"R6-promoted-own-then-foreign", "REFUSE", `import "crypto/x509"
type in struct{c *x509.Certificate}
type out struct{*in}
func probe(o out){o.c.Version++}`, "foreign pointee write forbidden: crypto/x509.Certificate"},
		{"R7-own-named-pointer-to-unnamed", "REFUSE", `type P *[1]int
func probe(p P){p[0]=1}`, "foreign pointee write forbidden: [1]int"},
		// Positive controls the fix must preserve.
		{"P1-own-identity-conversion", "POSITIVE", `type o struct{N int}
func probe(p *o){(*o)(p).N++}`, ""},
		{"P2-own-generic-receiver", "POSITIVE", `type box[T any] struct{v T}
func (b *box[T]) set(v T){b.v=v}
func probe(){(&box[int]{}).set(1)}`, ""},
		{"P3-untyped-nil", "POSITIVE", `type o struct{N int}
func probe(){_=(*o)(nil)}`, ""},
		{"P4-alias-identical-element", "POSITIVE", `type o struct{N int}
type Alias=o
type PointerAlias=*Alias
func probe(p *o){PointerAlias(p).N++}`, ""},
		{"P5-named-pointer-identical-element", "POSITIVE", `type o struct{N int}
type Pointer *o
func probe(p *o){Pointer(p).N++}`, ""},
		{"P6-unrelated-value-conversion", "POSITIVE", `type n int
func probe(){_=n(1)}`, ""},
	}
	for _, m := range cases {
		t.Run(m.name, func(t *testing.T) {
			src := copyMap(original)
			src["pl_review_probe.go"] = []byte("package migrationcontext\n" + m.code)
			buildPLMutation(t, root, src)
			checked, e := checkSourcePackage(ownImport, src, paths, nil)
			if e != nil {
				t.Fatal("actual built source must typecheck", e)
			}
			e = sourceEffects(src, checked)
			reason := "<nil>"
			if e != nil {
				reason = e.Error()
			}
			t.Logf("OWNER_PLR1C_PROBE case=%s kind=%s build=0 typecheck=0 refused=%t reason=%s", m.name, m.kind, e != nil, reason)
			assertPLReason(t, m.name, m.want != "", []string{m.want}, e)
		})
	}
}
