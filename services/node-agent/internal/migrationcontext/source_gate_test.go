package migrationcontext

// These gates inspect public tracked source with standard Go tools. They do not
// inspect private deployment state, install dependencies or invoke runtime APIs.
import (
	"bytes"
	"encoding/json"
	"fmt"
	"go/ast"
	"go/importer"
	"go/parser"
	"go/token"
	"go/types"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"sync"
	"testing"
)

const k1Base = "eb32b211ab3704935b9431747089ab0715582a74"
const k1Dir = "services/node-agent/migrationverify/"
const ownDir = "services/node-agent/internal/migrationcontext/"
const k1Import = "github.com/egparadise/SaintVision-Invion/services/node-agent/migrationverify"

func repository(t *testing.T) string {
	t.Helper()
	p, e := filepath.Abs("../../../..")
	if e != nil {
		t.Fatal(e)
	}
	return p
}
func sourceCommand(t *testing.T, dir string, name string, args ...string) []byte {
	t.Helper()
	c := exec.Command(name, args...)
	c.Dir = dir
	c.Env = append(os.Environ(), "GOTOOLCHAIN=local", "GOWORK=off", "GOPROXY=off", "GOSUMDB=off", "GOMAXPROCS=1")
	b, e := c.CombinedOutput()
	if e != nil {
		t.Fatalf("%s %v: %v\n%s", name, args, e, b)
	}
	return b
}
func sourceSet(t *testing.T, root, base string) map[string][]byte {
	t.Helper()
	var listed []byte
	if base == "" {
		listed = sourceCommand(t, root, "git", "ls-files", "--", k1Dir)
	} else {
		listed = sourceCommand(t, root, "git", "ls-tree", "-r", "--name-only", base, "--", k1Dir)
	}
	out := map[string][]byte{}
	for _, p := range strings.Fields(string(listed)) {
		if !strings.HasSuffix(p, ".go") || strings.HasSuffix(p, "_test.go") {
			continue
		}
		var b []byte
		var e error
		if base == "" {
			b, e = os.ReadFile(filepath.Join(root, filepath.FromSlash(p)))
			if e != nil {
				t.Fatal(e)
			}
		} else {
			b = sourceCommand(t, root, "git", "show", base+":"+p)
		}
		out[filepath.Base(p)] = b
	}
	if len(out) == 0 {
		t.Fatal("no actual package source")
	}
	return out
}

var exportsOnce sync.Once
var exportPaths map[string]string

func exports(t *testing.T, root string) map[string]string {
	t.Helper()
	exportsOnce.Do(func() {
		b := sourceCommand(t, filepath.Join(root, "services/node-agent"), "go", "list", "-p=1", "-export", "-deps", "-json", "./migrationverify")
		d := json.NewDecoder(bytes.NewReader(b))
		exportPaths = map[string]string{}
		for {
			var x struct{ ImportPath, Export string }
			e := d.Decode(&x)
			if e == io.EOF {
				break
			}
			if e != nil {
				t.Fatal(e)
			}
			if x.Export != "" {
				exportPaths[x.ImportPath] = x.Export
			}
		}
	})
	return exportPaths
}

type typeGraph struct {
	seen                              map[types.Type]int
	next                              int
	localTypes, localFields, embedded int
	err                               error
}

func (g *typeGraph) shape(t types.Type) string {
	if t == nil {
		g.err = fmt.Errorf("nil type")
		return "REFUSE"
	}
	if id, ok := g.seen[t]; ok {
		return fmt.Sprintf("ref#%d", id)
	}
	g.next++
	id := g.next
	g.seen[t] = id
	wrap := func(s string) string { return fmt.Sprintf("#%d{%s}", id, s) }
	switch x := t.(type) {
	case *types.Basic:
		return wrap("basic:" + x.Name())
	case *types.Named:
		pkg := ""
		if x.Obj().Pkg() != nil {
			pkg = x.Obj().Pkg().Path()
		}
		args := []string{}
		for i := 0; i < x.TypeArgs().Len(); i++ {
			args = append(args, g.shape(x.TypeArgs().At(i)))
		}
		if pkg == k1Import {
			g.localTypes++
			if st, ok := x.Underlying().(*types.Struct); ok {
				g.localFields += st.NumFields()
				for i := 0; i < st.NumFields(); i++ {
					if st.Field(i).Embedded() {
						g.embedded++
					}
				}
			}
		}
		params := []string{}
		for i := 0; i < x.TypeParams().Len(); i++ {
			params = append(params, g.shape(x.TypeParams().At(i)))
		}
		return wrap("named:" + pkg + "." + x.Obj().Name() + "[" + strings.Join(args, ",") + "]<" + strings.Join(params, ",") + ">=" + g.shape(x.Underlying()))
	case *types.Alias:
		args := []string{}
		for i := 0; i < x.TypeArgs().Len(); i++ {
			args = append(args, g.shape(x.TypeArgs().At(i)))
		}
		params := []string{}
		for i := 0; i < x.TypeParams().Len(); i++ {
			params = append(params, g.shape(x.TypeParams().At(i)))
		}
		return wrap("alias:" + x.Obj().Name() + "[" + strings.Join(args, ",") + "]<" + strings.Join(params, ",") + ">=" + g.shape(x.Rhs()))
	case *types.Struct:
		f := []string{}
		for i := 0; i < x.NumFields(); i++ {
			v := x.Field(i)
			pkg := ""
			if v.Pkg() != nil {
				pkg = v.Pkg().Path()
			}
			f = append(f, fmt.Sprintf("%s.%s:embedded=%t:exported=%t:tag=%q:%s", pkg, v.Name(), v.Embedded(), v.Exported(), x.Tag(i), g.shape(v.Type())))
		}
		return wrap("struct[" + strings.Join(f, ";") + "]")
	case *types.Map:
		return wrap("map[" + g.shape(x.Key()) + "]" + g.shape(x.Elem()))
	case *types.Slice:
		return wrap("slice:" + g.shape(x.Elem()))
	case *types.Array:
		return wrap(fmt.Sprintf("array:%d:%s", x.Len(), g.shape(x.Elem())))
	case *types.Pointer:
		return wrap("pointer:" + g.shape(x.Elem()))
	case *types.Signature:
		p := []string{}
		for i := 0; i < x.TypeParams().Len(); i++ {
			p = append(p, g.shape(x.TypeParams().At(i)))
		}
		return wrap(fmt.Sprintf("func:variadic=%t:typeparams=%s:params=%s:results=%s", x.Variadic(), strings.Join(p, ","), g.shape(x.Params()), g.shape(x.Results())))
	case *types.Tuple:
		a := []string{}
		for i := 0; i < x.Len(); i++ {
			a = append(a, g.shape(x.At(i).Type()))
		}
		return wrap("tuple[" + strings.Join(a, ",") + "]")
	case *types.Interface:
		x.Complete()
		a := []string{}
		for i := 0; i < x.NumExplicitMethods(); i++ {
			m := x.ExplicitMethod(i)
			a = append(a, m.FullName()+":"+g.shape(m.Type()))
		}
		for i := 0; i < x.NumEmbeddeds(); i++ {
			a = append(a, "embed:"+g.shape(x.EmbeddedType(i)))
		}
		return wrap("interface[" + strings.Join(a, ";") + "]")
	case *types.TypeParam:
		return wrap("typeparam:" + x.Obj().Name() + ":" + g.shape(x.Constraint()))
	case *types.Union:
		a := []string{}
		for i := 0; i < x.Len(); i++ {
			a = append(a, fmt.Sprintf("tilde=%t:%s", x.Term(i).Tilde(), g.shape(x.Term(i).Type())))
		}
		return wrap("union[" + strings.Join(a, "|") + "]")
	case *types.Chan:
		return wrap(fmt.Sprintf("chan:%d:%s", x.Dir(), g.shape(x.Elem())))
	default:
		g.err = fmt.Errorf("unhandled Go type %T", t)
		return "REFUSE"
	}
}

type census struct {
	shape                   string
	types, fields, embedded int
}

func packageCensus(src map[string][]byte, paths map[string]string) (census, error) {
	fset := token.NewFileSet()
	names := make([]string, 0, len(src))
	for p := range src {
		names = append(names, p)
	}
	sort.Strings(names)
	files := []*ast.File{}
	for _, name := range names {
		f, e := parser.ParseFile(fset, name, src[name], parser.AllErrors|parser.SkipObjectResolution)
		if e != nil {
			return census{}, e
		}
		files = append(files, f)
	}
	lookup := func(path string) (io.ReadCloser, error) {
		p, ok := paths[path]
		if !ok {
			return nil, fmt.Errorf("no actual export data for %s", path)
		}
		return os.Open(p)
	}
	cfg := types.Config{Importer: importer.ForCompiler(fset, "gc", lookup)}
	p, e := cfg.Check(k1Import, fset, files, nil)
	if e != nil {
		return census{}, e
	}
	obj, ok := p.Scope().Lookup("NewVerifier").(*types.Func)
	if !ok {
		return census{}, fmt.Errorf("missing NewVerifier")
	}
	sig, ok := obj.Type().(*types.Signature)
	if !ok || sig.Params().Len() != 2 {
		return census{}, fmt.Errorf("unknown constructor shape")
	}
	g := &typeGraph{seen: map[types.Type]int{}}
	parts := []string{types.TypeString(sig, func(p *types.Package) string { return p.Path() })}
	for i := 0; i < sig.Params().Len(); i++ {
		parts = append(parts, g.shape(sig.Params().At(i).Type()))
	}
	if g.err != nil {
		return census{}, g.err
	}
	return census{shape: strings.Join(parts, "\n"), types: g.localTypes, fields: g.localFields, embedded: g.embedded}, nil
}

func TestWholePackageFullUnderlyingCensus(t *testing.T) {
	root := repository(t)
	paths := exports(t, root)
	base := sourceSet(t, root, k1Base)
	current := sourceSet(t, root, "")
	want, e := packageCensus(base, paths)
	if e != nil {
		t.Fatal(e)
	}
	got, e := packageCensus(current, paths)
	if e != nil {
		t.Fatal(e)
	}
	if want.types != 13 || want.fields != 73 || want.embedded != 0 {
		t.Fatalf("unexpected immutable baseline %+v", want)
	}
	if got.shape != want.shape {
		t.Fatal("full underlying input/signature shape changed")
	}
	if len(current) != len(base) {
		t.Fatal("whole-package source coverage changed")
	}
	for name, b := range base {
		if hashBytes(current[name]) != hashBytes(b) {
			t.Fatalf("unreviewed K1 source: %s", name)
		}
	}
	t.Logf("actual full package: %d files, input types=%d fields=%d embedded=%d canonicalSHA256=%s; same-toolchain immutable baseline", len(base), got.types, got.fields, got.embedded, hashBytes([]byte(got.shape)))
}

func TestCensusMutantsAfterSimulatedRawRepin(t *testing.T) {
	root := repository(t)
	paths := exports(t, root)
	original := sourceSet(t, root, k1Base)
	control, e := packageCensus(original, paths)
	if e != nil {
		t.Fatal(e)
	}
	mutants := []struct{ id, old, next, extra string }{
		{"G01", "RegistrySHA256 string", "EmbeddedProbe\n RegistrySHA256 string", "type EmbeddedProbe struct{ Value string }"},
		{"G02", "RegistrySHA256 string", "*EmbeddedProbe\n RegistrySHA256 string", "type EmbeddedProbe struct{ Value string }"},
		{"G03", "Now                  time.Time", "Now                  any", ""},
		{"G04", "type InstalledTrust struct", "type installedTrust struct", "type InstalledTrust = installedTrust"},
		{"G05", "RegistrySHA256 string", "AddedField string\n RegistrySHA256 string", ""},
		{"G06", "Grants         []KeyGrant", "Grants         []AlternateGrant", "type AlternateGrant KeyGrant"},
		{"G07", "ContractPins   map[string]ContractPin", "ContractPins   map[string]any", ""},
		{"G08", "func NewVerifier(installed InstalledTrust, context TrustedContext)", "func NewVerifier(installed *InstalledTrust, context TrustedContext)", ""},
	}
	for _, m := range mutants {
		t.Run(m.id, func(t *testing.T) {
			src := copyMap(original)
			s := string(src["trust.go"])
			if !strings.Contains(s, m.old) {
				t.Fatal("mutant did not target actual source")
			}
			src["trust.go"] = []byte(strings.Replace(s, m.old, m.next, 1) + "\n" + m.extra)
			c, e := packageCensus(src, paths)
			if e == nil && c.shape == control.shape {
				t.Fatal("undetected mutation after raw repin")
			}
		})
	}
	// Reviewer counterexamples are TYPE-CORRECT both before and after the raw
	// repin. A named map/slice/function must include its full underlying type.
	for _, m := range []struct{ id, before, after string }{{"R01", "map[string]string", "map[string]any"}, {"R02", "[]string", "[]any"}, {"R03", "func() time.Time", "func() any"}} {
		t.Run(m.id, func(t *testing.T) {
			before := copyMap(original)
			name := "CensusProbe"
			extra := "type " + name + " " + m.before
			before["trust.go"] = []byte(strings.Replace(string(before["trust.go"]), "RegistrySHA256 string", "Probe "+name+"\n RegistrySHA256 string", 1) + "\n" + extra)
			a, e := packageCensus(before, paths)
			if e != nil {
				t.Fatal("control must typecheck", e)
			}
			after := copyMap(before)
			after["trust.go"] = []byte(strings.Replace(string(after["trust.go"]), extra, "type "+name+" "+m.after, 1))
			b, e := packageCensus(after, paths)
			if e != nil {
				t.Fatal("mutant must typecheck", e)
			}
			if a.shape == b.shape {
				t.Fatal("named underlying change missed")
			}
		})
	}
	// A newly reachable cross-file named generic shape is not an opaque stub.
	t.Run("cross-file-generic", func(t *testing.T) {
		src := copyMap(original)
		src["probe.go"] = []byte("package migrationverify\ntype Probe[T any] struct { Nested map[string][]T }\n")
		src["trust.go"] = []byte(strings.Replace(string(src["trust.go"]), "RegistrySHA256 string", "New Probe[string]\n RegistrySHA256 string", 1))
		a, e := packageCensus(src, paths)
		if e != nil {
			t.Fatal(e)
		}
		src["probe.go"] = bytes.ReplaceAll(src["probe.go"], []byte("[]T"), []byte("[]any"))
		b, e := packageCensus(src, paths)
		if e != nil {
			t.Fatal(e)
		}
		if a.shape == b.shape {
			t.Fatal("cross-file generic shape missed")
		}
	})
}

func TestRepositoryBoundaryAndZeroEffects(t *testing.T) {
	root := repository(t)
	listed := strings.Fields(string(sourceCommand(t, root, "git", "ls-files", "--", "*.go", ":(glob)**/go.mod")))
	paths := map[string]bool{}
	modules := []string{}
	for _, p := range listed {
		if filepath.Base(p) == "go.mod" {
			modules = append(modules, p)
		} else {
			paths[p] = true
		}
	}
	// Include the new package even before its first commit. Every other source
	// is tracked first-party source, across BOTH modules and all platform files.
	entries, e := os.ReadDir(filepath.Join(root, filepath.FromSlash(ownDir)))
	if e != nil {
		t.Fatal(e)
	}
	for _, f := range entries {
		if strings.HasSuffix(f.Name(), ".go") {
			paths[ownDir+f.Name()] = true
		}
	}
	if len(modules) != 2 {
		t.Fatalf("module coverage changed: %v", modules)
	}
	ordered := []string{}
	for p := range paths {
		ordered = append(ordered, p)
	}
	sort.Strings(ordered)
	prodImports, testImports, baselineDeclarations, constructors := []string{}, []string{}, []string{}, []string{}
	allowedImports := map[string]bool{"bytes": true, "crypto/ed25519": true, "crypto/x509": true, "crypto/sha256": true, "encoding/hex": true, "encoding/json": true, "strings": true, "time": true, "unicode/utf8": true, k1Import: true}
	for _, p := range ordered {
		b, e := os.ReadFile(filepath.Join(root, filepath.FromSlash(p)))
		if e != nil {
			t.Fatal(e)
		}
		fs := token.NewFileSet()
		f, e := parser.ParseFile(fs, p, b, parser.AllErrors|parser.SkipObjectResolution)
		if e != nil {
			t.Fatal(e)
		}
		isTest := strings.HasSuffix(p, "_test.go")
		isK1 := strings.HasPrefix(p, k1Dir)
		own := strings.HasPrefix(p, ownDir)
		aliases := map[string]bool{}
		for _, im := range f.Imports {
			path, e := strconv.Unquote(im.Path.Value)
			if e != nil {
				t.Fatal(e)
			}
			if own && !isTest && !allowedImports[path] {
				t.Fatalf("effect/bypass import forbidden in trusted closure: %s %s", p, path)
			}
			if isK1 && !isTest && (path == "unsafe" || path == "reflect" || path == "plugin") {
				t.Fatalf("K1 bypass import %s", path)
			}
			if path == k1Import {
				alias := "migrationverify"
				if im.Name != nil {
					alias = im.Name.Name
				}
				aliases[alias] = true
				if isTest {
					testImports = append(testImports, p+":"+alias)
					t.Fatalf("new K1 test importer needs explicit fixture review: %s", p)
				} else {
					prodImports = append(prodImports, p+":"+alias)
					if p != ownDir+"k1_bridge.go" || alias == "." || alias == "_" {
						t.Fatalf("unregistered K1 production importer: %s:%s", p, alias)
					}
				}
			}
		}
		if isK1 && !isTest {
			for _, d := range f.Decls {
				if fn, ok := d.(*ast.FuncDecl); ok && (fn.Name.Name == "NewVerifier" || fn.Name.Name == "Verify" || fn.Name.Name == "VerifyCurrentProjectionSet") {
					baselineDeclarations = append(baselineDeclarations, p+":"+fn.Name.Name)
				}
			}
		}
		if own && !isTest {
			for _, d := range f.Decls {
				if fn, ok := d.(*ast.FuncDecl); ok {
					if fn.Name.IsExported() {
						switch fn.Name.Name {
						case "NewService":
							if fn.Recv != nil || len(fn.Type.Params.List) != 0 {
								t.Fatal("public provider/clock injection")
							}
						case "LoadInstalledPolicy", "ReadHistory", "ValidateHistory", "Error", "Code":
							if fn.Recv == nil {
								t.Fatal("unexpected public constructor")
							}
						default:
							t.Fatalf("unreviewed exported API: %s", fn.Name.Name)
						}
					}
					switch fn.Name.Name {
					case "ReadCurrent", "DeriveCurrent", "CurrentView", "currentAssemble", "currentSnapshotToken":
						t.Fatalf("current API must be absent: %s", fn.Name.Name)
					}
				}
				if gd, ok := d.(*ast.GenDecl); ok {
					for _, sp := range gd.Specs {
						ts, ok := sp.(*ast.TypeSpec)
						if !ok {
							continue
						}
						if ts.Name.Name == "Service" || ts.Name.Name == "InstalledPolicy" || ts.Name.Name == "History" {
							st, ok := ts.Type.(*ast.StructType)
							if !ok || ts.Assign.IsValid() {
								t.Fatal("opaque type changed")
							}
							for _, field := range st.Fields.List {
								for _, name := range field.Names {
									if name.IsExported() {
										t.Fatal("exported trusted DTO/composition field")
									}
								}
								if len(field.Names) == 0 {
									t.Fatal("embedded opaque field")
								}
							}
						}
					}
				}
			}
			parents := map[ast.Node]ast.Node{}
			stack := []ast.Node{}
			ast.Inspect(f, func(n ast.Node) bool {
				if n == nil {
					stack = stack[:len(stack)-1]
					return false
				}
				if len(stack) > 0 {
					parents[n] = stack[len(stack)-1]
				}
				stack = append(stack, n)
				return true
			})
			ast.Inspect(f, func(n ast.Node) bool {
				if lit, ok := n.(*ast.CompositeLit); ok {
					if id, ok := lit.Type.(*ast.Ident); ok {
						switch id.Name {
						case "InstalledPolicy", "History", "policyBinding", "historyBinding":
							t.Fatal("production opaque-value issuer is not granted")
						}
					}
				}
				if sel, ok := n.(*ast.SelectorExpr); ok {
					if id, ok := sel.X.(*ast.Ident); ok {
						if id.Name == "time" && sel.Sel.Name == "After" {
							t.Fatal("physical clock timer forbidden")
						}
						if id.Name == "ed25519" && sel.Sel.Name != "PublicKey" {
							t.Fatal("only public-key type use is granted")
						}
					}
					switch sel.Sel.Name {
					case "Now", "AfterFunc", "Sleep", "Tick", "NewTicker", "NewTimer", "Sign", "SignMessage", "Unmarshal", "NewDecoder", "VerifyCurrentProjectionSet":
						t.Fatalf("effect/unchecked DTO/current selector forbidden in production slice: %s", sel.Sel.Name)
					}
					if id, ok := sel.X.(*ast.Ident); ok && aliases[id.Name] {
						switch sel.Sel.Name {
						case "NewVerifier":
							call, ok := parents[sel].(*ast.CallExpr)
							if !ok || call.Fun != sel {
								t.Fatal("constructor alias/reference forbidden")
							}
							constructors = append(constructors, p+":NewVerifier")
						case "InstalledTrust", "TrustedContext":
							if _, ok := parents[sel].(*ast.CompositeLit); !ok {
								t.Fatal("unchecked K1 DTO reference")
							}
							constructors = append(constructors, p+":"+sel.Sel.Name)
						case "VerifyCurrentProjectionSet", "CurrentProjectionContext", "CurrentNativeWitness":
							t.Fatal("current bridge forbidden")
						}
					}
				}
				return true
			})
		}
	}
	if len(prodImports) != 1 || len(constructors) != 3 || len(baselineDeclarations) != 3 {
		t.Fatalf("unexpected boundary census imports=%v construction=%v baseline=%v", prodImports, constructors, baselineDeclarations)
	}
	t.Logf("repo modules=%v; Go files=%d; production imports=%v; test imports=%v; immutable K1 definitions=%v; sole bridge sites=%v", modules, len(ordered), prodImports, testImports, baselineDeclarations, constructors)
}
