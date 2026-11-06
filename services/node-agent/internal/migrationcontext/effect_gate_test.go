package migrationcontext

import (
	"fmt"
	"go/ast"
	"go/importer"
	"go/parser"
	"go/token"
	"go/types"
	"io"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"testing"
)

const ownImport = "github.com/egparadise/SaintVision-Invion/services/node-agent/internal/migrationcontext"

type checkedSource struct {
	pkg   *types.Package
	info  *types.Info
	files []*ast.File
	fset  *token.FileSet
}

func checkSourcePackage(path string, src map[string][]byte, exports map[string]string, k1 *types.Package) (checkedSource, error) {
	fs := token.NewFileSet()
	names := []string{}
	for n := range src {
		if strings.HasSuffix(n, ".go") && !strings.HasSuffix(n, "_test.go") {
			names = append(names, n)
		}
	}
	sort.Strings(names)
	files := []*ast.File{}
	for _, n := range names {
		f, e := parser.ParseFile(fs, n, src[n], parser.ParseComments|parser.AllErrors|parser.SkipObjectResolution)
		if e != nil {
			return checkedSource{}, e
		}
		files = append(files, f)
	}
	lookup := func(p string) (io.ReadCloser, error) {
		file, ok := exports[p]
		if !ok {
			return nil, fmt.Errorf("missing actual export %s", p)
		}
		return os.Open(file)
	}
	imp := importer.ForCompiler(fs, "gc", lookup)
	cfg := types.Config{Importer: packageImporter{fallback: imp, k1: k1}}
	info := &types.Info{Types: map[ast.Expr]types.TypeAndValue{}, Defs: map[*ast.Ident]types.Object{}, Uses: map[*ast.Ident]types.Object{}, Selections: map[*ast.SelectorExpr]*types.Selection{}}
	p, e := cfg.Check(path, fs, files, info)
	if e != nil {
		return checkedSource{}, e
	}
	return checkedSource{pkg: p, info: info, files: files, fset: fs}, nil
}

type packageImporter struct {
	fallback types.Importer
	k1       *types.Package
}

func (i packageImporter) Import(path string) (*types.Package, error) {
	if path == k1Import && i.k1 != nil {
		return i.k1, nil
	}
	return i.fallback.Import(path)
}

func ownProductionSources(t *testing.T, root string) map[string][]byte {
	t.Helper()
	out := map[string][]byte{}
	dir := filepath.Join(root, filepath.FromSlash(ownDir))
	e := filepath.WalkDir(dir, func(path string, d os.DirEntry, e error) error {
		if e != nil {
			return e
		}
		if d.IsDir() {
			return nil
		}
		rel, e := filepath.Rel(dir, path)
		if e != nil {
			return e
		}
		b, e := os.ReadFile(path)
		if e != nil {
			return e
		}
		out[filepath.ToSlash(rel)] = b
		return nil
	})
	if e != nil {
		t.Fatal(e)
	}
	return out
}

func objectID(obj types.Object) string {
	if obj == nil {
		return "<unresolved>"
	}
	pkg := ""
	if obj.Pkg() != nil {
		pkg = obj.Pkg().Path()
	}
	if f, ok := obj.(*types.Func); ok {
		sig := f.Type().(*types.Signature)
		if sig.Recv() != nil {
			r := types.Unalias(sig.Recv().Type())
			if p, ok := r.(*types.Pointer); ok {
				r = types.Unalias(p.Elem())
			}
			if n, ok := r.(*types.Named); ok {
				return pkg + "." + n.Obj().Name() + "." + f.Name()
			}
		}
	}
	return pkg + "." + obj.Name()
}

// Exact CURRENT pure object allowlist, independent of spelling/import aliases.
// There is deliberately no strings.* or time.* wildcard. Function references
// are checked too, so assigning time.Since to a variable does not hide it.
var pureExternalObjects = map[string]bool{
	"bytes.Equal": true, "crypto/sha256.Sum256": true,
	"encoding/hex.EncodeToString": true, "encoding/hex.DecodeString": true,
	"encoding/json.Marshal": true, "encoding/json.Valid": true,
	"crypto/x509.ParseCertificate": true, "crypto/x509.Certificate.CheckSignatureFrom": true,
	"net/url.URL.String":       true,
	"unicode/utf8.ValidString": true, "strings.ToLower": true, "strings.Trim": true,
	"time.Time.IsZero": true, "time.Time.Location": true, "time.Time.Before": true, "time.Time.After": true, "time.Time.Sub": true,
	k1Import + ".CanonicalJSON": true, k1Import + ".NewVerifier": true, k1Import + ".Verifier.Verify": true,
}

func rejectNativeSources(src map[string][]byte) error {
	native := map[string]bool{".s": true, ".syso": true, ".c": true, ".h": true, ".cc": true, ".cpp": true, ".cxx": true, ".hpp": true, ".m": true, ".mm": true, ".f": true, ".f90": true, ".sx": true, ".o": true, ".a": true, ".obj": true, ".dll": true, ".so": true, ".dylib": true}
	for name := range src {
		if native[strings.ToLower(filepath.Ext(name))] {
			return fmt.Errorf("native package source forbidden: %s", name)
		}
	}
	return nil
}
func sourceEffects(src map[string][]byte, checked checkedSource) error {
	if e := rejectNativeSources(src); e != nil {
		return e
	}
	for name, b := range src {
		if strings.HasSuffix(name, ".go") && !strings.HasSuffix(name, "_test.go") {
			for _, tag := range []string{"//go:linkname", "//go:cgo_", "//go:wasmimport", "//go:wasmexport"} {
				if strings.Contains(string(b), tag) {
					return fmt.Errorf("linker/native directive forbidden")
				}
			}
		}
	}
	for _, f := range checked.files {
		for _, d := range f.Decls {
			if fn, ok := d.(*ast.FuncDecl); ok && fn.Body == nil {
				return fmt.Errorf("bodyless function forbidden: %s", fn.Name.Name)
			}
		}
	}
	for _, obj := range checked.info.Uses {
		if f, ok := obj.(*types.Func); ok && f.Pkg() != nil && f.Pkg().Path() != ownImport && !pureExternalObjects[objectID(f)] {
			return fmt.Errorf("unreviewed function/method object: %s", objectID(f))
		}
	}
	var failure error
	for _, f := range checked.files {
		ast.Inspect(f, func(n ast.Node) bool {
			if failure != nil {
				return false
			}
			switch n.(type) {
			case *ast.GoStmt, *ast.SendStmt:
				failure = fmt.Errorf("asynchronous execution/channel effect forbidden")
				return false
			}
			if call, ok := n.(*ast.CallExpr); ok {
				if checked.info.Types[call.Fun].IsType() {
					return true
				}
				fun := call.Fun
				for {
					switch x := fun.(type) {
					case *ast.IndexExpr:
						fun = x.X
						continue
					case *ast.IndexListExpr:
						fun = x.X
						continue
					case *ast.ParenExpr:
						fun = x.X
						continue
					}
					break
				}
				var obj types.Object
				switch x := fun.(type) {
				case *ast.Ident:
					obj = checked.info.Uses[x]
				case *ast.SelectorExpr:
					if s := checked.info.Selections[x]; s != nil {
						obj = s.Obj()
					} else {
						obj = checked.info.Uses[x.Sel]
					}
				}
				switch x := obj.(type) {
				case *types.Func:
					if x.Pkg() == nil || x.Pkg().Path() != ownImport && !pureExternalObjects[objectID(x)] {
						failure = fmt.Errorf("unreviewed call: %s", objectID(x))
					}
				case *types.Builtin:
					if x.Name() != "append" && x.Name() != "len" && x.Name() != "make" {
						failure = fmt.Errorf("unreviewed builtin: %s", x.Name())
					}
				default:
					failure = fmt.Errorf("unresolved/function-value/callback call forbidden")
				}
			}
			if a, ok := n.(*ast.AssignStmt); ok {
				for _, lhs := range a.Lhs {
					if s, ok := lhs.(*ast.SelectorExpr); ok {
						if v, ok := checked.info.Uses[s.Sel].(*types.Var); ok && checked.info.Selections[s] == nil && v.Pkg() != nil && v.Pkg().Path() != ownImport {
							failure = fmt.Errorf("foreign state write forbidden")
						}
					}
				}
			}
			return failure == nil
		})
	}
	return failure
}

func TestResolvedObjectEffectBoundary(t *testing.T) {
	requireResolvedEffectBoundary(t, repository(t))
}
func requireResolvedEffectBoundary(t *testing.T, root string) {
	t.Helper()
	src := ownProductionSources(t, root)
	checked, e := checkSourcePackage(ownImport, src, exports(t, root), nil)
	if e != nil {
		t.Fatal(e)
	}
	if e = sourceEffects(src, checked); e != nil {
		t.Fatal(e)
	}
	// K1 is the other production package in this reviewed closure. Its raw Go
	// pins alone must not permit an added native linker input beside those files.
	k1Files := map[string][]byte{}
	e = filepath.WalkDir(filepath.Join(root, filepath.FromSlash(k1Dir)), func(path string, d os.DirEntry, e error) error {
		if e != nil {
			return e
		}
		if d.IsDir() {
			return nil
		}
		rel, e := filepath.Rel(root, path)
		if e != nil {
			return e
		}
		k1Files[filepath.ToSlash(rel)] = nil
		return nil
	})
	if e != nil {
		t.Fatal(e)
	}
	if e = rejectNativeSources(k1Files); e != nil {
		t.Fatal(e)
	}
}

func TestReviewR1CompileValidEffectAndAliasMutants(t *testing.T) {
	root := repository(t)
	original := ownProductionSources(t, root)
	paths := exports(t, root)
	control, e := checkSourcePackage(ownImport, original, paths, nil)
	if e != nil {
		t.Fatal(e)
	}
	if e = sourceEffects(original, control); e != nil {
		t.Fatal("actual pure control must pass before mutants", e)
	}
	mutants := []struct{ name, code string }{
		{"aliased-time-Since", `import clock "time";func probe(){_ = clock.Since(clock.Time{})}`},
		{"aliased-time-Now", `import clock "time";func probe(){_ = clock.Now()}`},
		{"aliased-time-Until", `import clock "time";func probe(){_ = clock.Until(clock.Time{})}`},
		{"function-alias-clock", `import clock "time";func probe(){f:=clock.Since;_ = f(clock.Time{})}`},
		{"time-After", `import clock "time";func probe(){_ = clock.After(0)}`},
		{"time-AfterFunc", `import clock "time";func probe(){_ = clock.AfterFunc(0,func(){})}`},
		{"time-NewTimer", `import clock "time";func probe(){_ = clock.NewTimer(0)}`},
		{"time-NewTicker", `import clock "time";func probe(){_ = clock.NewTicker(1)}`},
		{"time-Tick", `import clock "time";func probe(){_ = clock.Tick(1)}`},
		{"aliased-seed", `import ed "crypto/ed25519";func probe(){_ = ed.NewKeyFromSeed(make([]byte,32))}`},
		{"aliased-generate", `import ed "crypto/ed25519";func probe(){_,_,_ = ed.GenerateKey(nil)}`},
		{"aliased-sign", `import ed "crypto/ed25519";func probe(){_ = ed.Sign(nil,nil)}`},
		{"create-certificate", `import cert "crypto/x509";func probe(){_,_ = cert.CreateCertificate(nil,nil,nil,nil,nil)}`},
		{"certificate-ambient-Verify", `import cert "crypto/x509";func probe(c *cert.Certificate){_,_ = c.Verify(cert.VerifyOptions{})}`},
		{"certificate-method-expression", `import cert "crypto/x509";func probe(c *cert.Certificate){f:=(*cert.Certificate).Verify;_,_ = f(c,cert.VerifyOptions{})}`},
		{"system-roots", `import cert "crypto/x509";func probe(){_,_ = cert.SystemCertPool()}`},
		{"unreviewed-pure-strings", `import text "strings";func probe(){_ = text.TrimSpace("x")}`},
		{"bodyless", `func probe()`},
		{"builtin-output", `func probe(){println("private")}`},
		{"asynchronous-execution", `func probe(){go probe()}`},
		{"linkname", `//go:linkname probe elsewhere
func probe()`},
	}
	for _, m := range mutants {
		t.Run(m.name, func(t *testing.T) {
			src := copyMap(original)
			src["probe.go"] = []byte("package migrationcontext\n" + m.code)
			checked, e := checkSourcePackage(ownImport, src, paths, nil)
			if e != nil {
				t.Fatal("mutant must typecheck, not merely syntax-fail", e)
			}
			if e = sourceEffects(src, checked); e == nil {
				t.Fatal("effect mutant escaped resolved boundary")
			}
		})
	}
	t.Run("pure-alias-control", func(t *testing.T) {
		src := copyMap(original)
		src["probe.go"] = []byte(`package migrationcontext
import text "strings";func probe(){_ = text.Trim("x","x")}`)
		checked, e := checkSourcePackage(ownImport, src, paths, nil)
		if e != nil {
			t.Fatal(e)
		}
		if e = sourceEffects(src, checked); e != nil {
			t.Fatal(e)
		}
	})
	for _, ext := range []string{".s", ".S", ".syso", ".c", ".h", ".cc", ".o"} {
		t.Run("native"+ext, func(t *testing.T) {
			src := copyMap(original)
			src["native"+ext] = []byte("native source fixture")
			checked, e := checkSourcePackage(ownImport, src, paths, nil)
			if e != nil {
				t.Fatal(e)
			}
			if sourceEffects(src, checked) == nil {
				t.Fatal("native source escaped")
			}
		})
	}
	t.Run("assembly-compiles-but-refuses", func(t *testing.T) {
		dir := t.TempDir()
		for n, b := range map[string]string{"go.mod": "module nativefixture\ngo 1.23\n", "native.go": "package nativefixture\nfunc Native()\n", "native_amd64.s": "TEXT ·Native(SB),$0-0\n RET\n"} {
			if e := os.WriteFile(filepath.Join(dir, n), []byte(b), 0600); e != nil {
				t.Fatal(e)
			}
		}
		sourceCommand(t, dir, "go", "build", "-p=1", "-o", filepath.Join(dir, "fixture.a"), ".")
		src := copyMap(original)
		src["native.go"] = []byte("package migrationcontext\nfunc Native()\n")
		src["native_amd64.s"] = []byte("TEXT ·Native(SB),$0-0\n RET\n")
		checked, e := checkSourcePackage(ownImport, src, paths, nil)
		if e != nil {
			t.Fatal(e)
		}
		if sourceEffects(src, checked) == nil {
			t.Fatal("compiled assembly path escaped")
		}
	})
}
