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
	// D04 grant msg_ccd8401cb2c5: deterministic epoch projection only.
	"time.Unix": true, "time.Time.UTC": true,
	k1Import + ".CanonicalJSON": true, k1Import + ".NewVerifier": true, k1Import + ".Verifier.Verify": true,
}

const h12SignatureSource = "h12_signature_internal.go"

type h12ScopedUses struct {
	references map[token.Pos]bool
	calls      map[token.Pos]bool
}

// This is a position/object/direct-call exception, NOT a package-wide allowance.
// Unadjusted positions deliberately ignore //line filename impersonation.
func h12ScopedCryptoUses(checked checkedSource) (h12ScopedUses, error) {
	allowed := h12ScopedUses{references: map[token.Pos]bool{}, calls: map[token.Pos]bool{}}
	parents := map[ast.Node]ast.Node{}
	for _, f := range checked.files {
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
	}
	owner := func(id *ast.Ident) string {
		for n := ast.Node(id); n != nil; n = parents[n] {
			if _, ok := n.(*ast.FuncLit); ok {
				return "" // No nested wrapper/callback exception.
			}
			if fn, ok := n.(*ast.FuncDecl); ok {
				if fn.Recv == nil && checked.info.Defs[fn.Name] == checked.pkg.Scope().Lookup(fn.Name.Name) {
					return fn.Name.Name
				}
				return ""
			}
		}
		return ""
	}
	for id, obj := range checked.info.Uses {
		key := objectID(obj)
		pos := checked.fset.PositionFor(id.Pos(), false)
		file := filepath.ToSlash(pos.Filename)
		// This new type restriction belongs only to the new H12 source. Other
		// source keeps its pre-existing DATA/pointee/conversion rules and limits.
		if typ, ok := obj.(*types.TypeName); ok && file == h12SignatureSource && typ.Pkg() != nil && typ.Pkg().Path() == "crypto/ed25519" {
			sel, selector := parents[id].(*ast.SelectorExpr)
			assertion, asserted := parents[sel].(*ast.TypeAssertExpr)
			dataAssertion := selector && sel.Sel == id && asserted && assertion.Type == sel
			if key != "crypto/ed25519.PublicKey" || !dataAssertion || owner(id) != "h12CheckRegistrySignature" {
				return allowed, fmt.Errorf("h12 crypto type scope forbidden: %s at %s", key, file)
			}
		}
		switch key {
		case "crypto/ed25519.Verify", "crypto/x509.ParsePKIXPublicKey", "crypto/x509.MarshalPKIXPublicKey":
			if _, ok := obj.(*types.Func); !ok || file != h12SignatureSource {
				return allowed, fmt.Errorf("h12 crypto source path forbidden: %s at %s", key, file)
			}
			if owner(id) != "h12CheckRegistrySignature" {
				return allowed, fmt.Errorf("h12 crypto helper scope forbidden: %s", key)
			}
			var expr ast.Node = id
			if sel, ok := parents[id].(*ast.SelectorExpr); ok && sel.Sel == id {
				expr = sel
			}
			call, ok := parents[expr].(*ast.CallExpr)
			if !ok || call.Fun != expr {
				return allowed, fmt.Errorf("h12 crypto non-direct reference forbidden: %s", key)
			}
			allowed.references[id.Pos()] = true
			allowed.calls[call.Pos()] = true
		}
	}
	return allowed, nil
}

func h12ResolvedVerifyAt(checked checkedSource, allowed h12ScopedUses, line, column int) bool {
	for id, obj := range checked.info.Uses {
		p := checked.fset.PositionFor(id.Pos(), false)
		if filepath.ToSlash(p.Filename) == h12SignatureSource && p.Line == line && p.Column == column && objectID(obj) == "crypto/ed25519.Verify" && allowed.references[id.Pos()] {
			return true
		}
	}
	return false
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

func interfaceReceiver(t types.Type) bool {
	t = types.Unalias(t)
	if p, ok := t.(*types.Pointer); ok {
		t = types.Unalias(p.Elem())
	}
	if _, ok := t.(*types.TypeParam); ok {
		return true
	}
	_, ok := t.Underlying().(*types.Interface)
	return ok
}

func closedOwnInterface(t types.Type, seen map[types.Type]bool) error {
	if t == nil || seen[t] {
		return nil
	}
	seen[t] = true
	if p, ok := types.Unalias(t).(*types.TypeParam); ok {
		return closedOwnInterface(p.Constraint(), seen)
	}
	u := types.Unalias(t)
	iface, ok := u.Underlying().(*types.Interface)
	if !ok {
		return nil
	}
	if n, ok := u.(*types.Named); ok && n.Obj().Pkg() != nil && n.Obj().Pkg().Path() != ownImport {
		return fmt.Errorf("foreign embedded interface forbidden: %s", objectID(n.Obj()))
	}
	iface.Complete()
	for i := 0; i < iface.NumMethods(); i++ {
		m := iface.Method(i)
		if m.Exported() || m.Pkg() == nil || m.Pkg().Path() != ownImport {
			return fmt.Errorf("interface/constraint method must be unexported own object: %s", objectID(m))
		}
	}
	for i := 0; i < iface.NumEmbeddeds(); i++ {
		if e := closedOwnInterface(iface.EmbeddedType(i), seen); e != nil {
			return e
		}
	}
	return nil
}

func foreignPackageVar(obj types.Object) *types.Var {
	v, ok := obj.(*types.Var)
	if !ok || v.IsField() || v.Pkg() == nil || v.Pkg().Path() == ownImport {
		return nil
	}
	if v.Pkg().Scope().Lookup(v.Name()) != v {
		return nil
	}
	return v
}

func usedObject(expr ast.Expr, info *types.Info) types.Object {
	for {
		if p, ok := expr.(*ast.ParenExpr); ok {
			expr = p.X
			continue
		}
		break
	}
	switch x := expr.(type) {
	case *ast.Ident:
		return info.Uses[x]
	case *ast.SelectorExpr:
		if s := info.Selections[x]; s != nil {
			return s.Obj()
		}
		return info.Uses[x.Sel]
	}
	return nil
}

// A declared own pointee is a conservative TYPE boundary, not proof of memory
// provenance. In particular, a local name/parameter or a pure call returning a
// pointer does not establish ownership. No whole-program alias analysis here.
func ownPointeeWrite(t types.Type) error {
	if t != nil {
		t = types.Unalias(t)
		if n, ok := t.(*types.Named); ok && n.Obj().Pkg() != nil && n.Obj().Pkg().Path() == ownImport {
			return nil
		}
		return fmt.Errorf("foreign pointee write forbidden: %s", types.TypeString(t, nil))
	}
	return fmt.Errorf("foreign pointee write forbidden: unresolved type")
}

func pointerElement(t types.Type) (types.Type, bool) {
	if t != nil {
		if p, ok := types.Unalias(t).Underlying().(*types.Pointer); ok {
			return p.Elem(), true
		}
	}
	return nil, false
}

// conversionPointerElements returns every pointer element a conversion target
// can denote: the target itself, or each pointer term of a type parameter's
// constraint type set (recursively through embedded interfaces and unions).
func conversionPointerElements(t types.Type, out []types.Type) []types.Type {
	if t == nil {
		return out
	}
	switch x := types.Unalias(t).(type) {
	case *types.TypeParam:
		return conversionPointerElements(x.Constraint(), out)
	case *types.Union:
		for i := 0; i < x.Len(); i++ {
			out = conversionPointerElements(x.Term(i).Type(), out)
		}
		return out
	}
	if iface, ok := types.Unalias(t).Underlying().(*types.Interface); ok {
		for i := 0; i < iface.NumEmbeddeds(); i++ {
			out = conversionPointerElements(iface.EmbeddedType(i), out)
		}
		return out
	}
	if e, ok := pointerElement(t); ok {
		out = append(out, e)
	}
	return out
}

func writeTargetBoundary(expr ast.Expr, info *types.Info) error {
	if expr == nil {
		return nil
	}
	if v := foreignPackageVar(usedObject(expr, info)); v != nil {
		return fmt.Errorf("foreign state write forbidden: %s", objectID(v))
	}
	switch x := expr.(type) {
	case *ast.ParenExpr:
		return writeTargetBoundary(x.X, info)
	case *ast.StarExpr:
		if e := ownPointeeWrite(info.TypeOf(x)); e != nil {
			return e
		}
		return writeTargetBoundary(x.X, info)
	case *ast.IndexExpr:
		// Go also implicitly dereferences pointers to arrays in index writes.
		if elem, ok := pointerElement(info.TypeOf(x.X)); ok {
			if e := ownPointeeWrite(elem); e != nil {
				return e
			}
		}
		return writeTargetBoundary(x.X, info)
	case *ast.SliceExpr:
		// An index target may be rooted in a slice expression, e.g. (*p)[:][i].
		// Continue to the pointer root rather than treating the slice as local.
		if elem, ok := pointerElement(info.TypeOf(x.X)); ok {
			if e := ownPointeeWrite(elem); e != nil {
				return e
			}
		}
		return writeTargetBoundary(x.X, info)
	case *ast.SelectorExpr:
		// Resolve the complete field path: a promoted field can implicitly
		// dereference an embedded foreign pointer even when x.X is an own value.
		if sel := info.Selections[x]; sel != nil && sel.Kind() == types.FieldVal {
			t := info.TypeOf(x.X)
			for _, index := range sel.Index() {
				if elem, ok := pointerElement(t); ok {
					if e := ownPointeeWrite(elem); e != nil {
						return e
					}
					t = elem
				}
				if t == nil {
					return fmt.Errorf("foreign pointee write forbidden: unresolved field path")
				}
				s, ok := types.Unalias(t).Underlying().(*types.Struct)
				if !ok || index >= s.NumFields() {
					return fmt.Errorf("foreign pointee write forbidden: unresolved field path")
				}
				t = s.Field(index).Type()
			}
		}
		return writeTargetBoundary(x.X, info)
	}
	return nil
}

func sourceEffects(src map[string][]byte, checked checkedSource) error {
	if e := rejectNativeSources(src); e != nil {
		return e
	}
	h12, e := h12ScopedCryptoUses(checked)
	if e != nil {
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
	seenInterfaces := map[types.Type]bool{}
	for _, obj := range checked.info.Defs {
		if n, ok := obj.(*types.TypeName); ok && n.Pkg() != nil && n.Pkg().Path() == ownImport {
			if e := closedOwnInterface(n.Type(), seenInterfaces); e != nil {
				return e
			}
		}
	}
	for expr, tv := range checked.info.Types {
		if _, ok := expr.(*ast.InterfaceType); ok {
			if e := closedOwnInterface(tv.Type, seenInterfaces); e != nil {
				return e
			}
		}
	}
	for id, obj := range checked.info.Uses {
		if v := foreignPackageVar(obj); v != nil && objectID(v) != "time.UTC" {
			return fmt.Errorf("foreign package variable read forbidden: %s", objectID(v))
		}
		if f, ok := obj.(*types.Func); ok && f.Pkg() != nil && f.Pkg().Path() == ownImport {
			sig := f.Type().(*types.Signature)
			if sig.Recv() != nil && interfaceReceiver(sig.Recv().Type()) && f.Exported() {
				return fmt.Errorf("exported own interface/constraint dispatch forbidden: %s", objectID(f))
			}
		}
		if f, ok := obj.(*types.Func); ok && f.Pkg() != nil && f.Pkg().Path() != ownImport && !pureExternalObjects[objectID(f)] && !h12.references[id.Pos()] {
			return fmt.Errorf("unreviewed function/method object: %s", objectID(f))
		}
	}
	var failure error
	for _, f := range checked.files {
		ast.Inspect(f, func(n ast.Node) bool {
			if failure != nil {
				return false
			}
			if u, ok := n.(*ast.UnaryExpr); ok && u.Op == token.AND {
				if v := foreignPackageVar(usedObject(u.X, checked.info)); v != nil {
					failure = fmt.Errorf("foreign package variable address forbidden: %s", objectID(v))
					return false
				}
			}
			switch n.(type) {
			case *ast.GoStmt, *ast.SendStmt:
				failure = fmt.Errorf("asynchronous execution/channel effect forbidden")
				return false
			}
			if call, ok := n.(*ast.CallExpr); ok {
				if tv := checked.info.Types[call.Fun]; tv.IsType() {
					// Pointer conversions must preserve element identity. An own
					// defined pointee name cannot confer ownership of a foreign
					// address, nor can a slice become an own array pointer here.
					for _, dst := range conversionPointerElements(tv.Type, nil) {
						var operand types.Type
						if len(call.Args) == 1 {
							operand = checked.info.TypeOf(call.Args[0])
						}
						nilOperand := false
						if b, ok := operand.(*types.Basic); ok {
							nilOperand = b.Kind() == types.UntypedNil
						}
						if !nilOperand {
							src, ok := pointerElement(operand)
							if !ok || !types.Identical(src, dst) {
								failure = fmt.Errorf("pointee-changing pointer conversion forbidden: %s", types.TypeString(tv.Type, nil))
								return false
							}
						}
					}
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
					if x.Pkg() == nil || x.Pkg().Path() != ownImport && !pureExternalObjects[objectID(x)] && !h12.calls[call.Pos()] {
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
			var targets []ast.Expr
			switch x := n.(type) {
			case *ast.AssignStmt:
				targets = x.Lhs
			case *ast.RangeStmt:
				if x.Tok == token.ASSIGN {
					targets = []ast.Expr{x.Key, x.Value}
				}
			case *ast.IncDecStmt:
				targets = []ast.Expr{x.X}
			}
			for _, target := range targets {
				if e := writeTargetBoundary(target, checked.info); e != nil {
					failure = e
					break
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

// Compile the stdlib-only source probe with the REAL compiler before crediting
// a guard denial. This is an isolated mutant fixture, never a replacement/stub
// for either real repository module or its contracts/export dependencies.
func h12CompileGuardProbe(t *testing.T, root, name, code string) checkedSource {
	t.Helper()
	dir := t.TempDir()
	module := []byte("module " + ownImport + "\n\ngo 1.23\n")
	if e := os.WriteFile(filepath.Join(dir, "go.mod"), module, 0600); e != nil {
		t.Fatal(e)
	}
	if e := os.WriteFile(filepath.Join(dir, name), []byte(code), 0600); e != nil {
		t.Fatal(e)
	}
	sourceCommand(t, dir, "go", "build", "-p=1", "-mod=readonly", "-o", filepath.Join(dir, "probe.a"), ".")
	checked, e := checkSourcePackage(ownImport, map[string][]byte{name: []byte(code)}, exports(t, root), nil)
	if e != nil {
		t.Fatal("guard probe must compile AND resolve actual exported types", e)
	}
	return checked
}

func TestH12ScopedCryptoObjectBoundary(t *testing.T) {
	root := repository(t)
	original := ownProductionSources(t, root)
	checked, e := checkSourcePackage(ownImport, original, exports(t, root), nil)
	if e != nil {
		t.Fatal(e)
	}
	if e = sourceEffects(original, checked); e != nil {
		t.Fatal("real unchanged-closure control", e)
	}
	verify := `package migrationcontext
import ed "crypto/ed25519"
func h12CheckRegistrySignature(){_ = ed.Verify([]byte(nil),nil,nil)}
`
	cases := []struct {
		name, file, code, cause string
		allowed                 bool
	}{
		{"same-file-direct-import-alias", h12SignatureSource, verify, "", true},
		{"foreign-file-direct-call", "h12_foreign.go", verify, "h12 crypto source path", false},
		{"foreign-file-aliased-PKIX", "h12_foreign.go", `package migrationcontext
import cert "crypto/x509"
func h12CheckRegistrySignature(){_,_ = cert.ParsePKIXPublicKey(nil)}
`, "h12 crypto source path", false},
		{"line-directive-cannot-impersonate", "h12_foreign.go", "package migrationcontext\nimport ed \"crypto/ed25519\"\n//line h12_signature_internal.go:1\nfunc h12CheckRegistrySignature(){_ = ed.Verify([]byte(nil),nil,nil)}\n", "h12 crypto source path", false},
		{"function-value-capture", h12SignatureSource, `package migrationcontext
import ed "crypto/ed25519"
func h12CheckRegistrySignature(){f:=ed.Verify;_ = f}
`, "h12 crypto non-direct reference", false},
		{"noncall-PKIX-reference", h12SignatureSource, `package migrationcontext
import cert "crypto/x509"
func h12CheckRegistrySignature(){_ = cert.MarshalPKIXPublicKey}
`, "h12 crypto non-direct reference", false},
		{"pass-function-as-argument", h12SignatureSource, `package migrationcontext
import cert "crypto/x509"
func consume(_ func([]byte)(any,error)){}
func h12CheckRegistrySignature(){consume(cert.ParsePKIXPublicKey)}
`, "h12 crypto non-direct reference", false},
		{"different-function-wrapper", h12SignatureSource, `package migrationcontext
import ed "crypto/ed25519"
func wrapper(){_ = ed.Verify([]byte(nil),nil,nil)}
`, "h12 crypto helper scope", false},
		{"nested-function-wrapper", h12SignatureSource, `package migrationcontext
import ed "crypto/ed25519"
func h12CheckRegistrySignature(){_ = func(){_ = ed.Verify([]byte(nil),nil,nil)}}
`, "h12 crypto helper scope", false},
		{"unapproved-method-value", h12SignatureSource, `package migrationcontext
import cert "crypto/x509"
func h12CheckRegistrySignature(c *cert.Certificate){_ = c.Verify}
`, "crypto/x509.Certificate.Verify", false},
		{"private-key-type-not-DATA", h12SignatureSource, `package migrationcontext
import ed "crypto/ed25519"
func h12CheckRegistrySignature(k ed.PrivateKey){_ = k}
`, "h12 crypto type scope", false},
		{"all-three-direct-control", h12SignatureSource, `package migrationcontext
import ed "crypto/ed25519"
import cert "crypto/x509"
func h12CheckRegistrySignature(){p,_:=cert.ParsePKIXPublicKey(nil);k,_:=p.(ed.PublicKey);_,_=cert.MarshalPKIXPublicKey(k);_=ed.Verify(k,nil,nil)}
`, "", true},
	}
	for _, x := range cases {
		t.Run(x.name, func(t *testing.T) {
			checked := h12CompileGuardProbe(t, root, x.file, x.code)
			e := sourceEffects(map[string][]byte{x.file: []byte(x.code)}, checked)
			if x.allowed {
				if e != nil {
					t.Fatal("direct scoped control", e)
				}
			} else if e == nil || !strings.Contains(e.Error(), x.cause) {
				t.Fatal("wrong causal source refusal", x.cause, e)
			}
			t.Logf("H12_GUARD_CASE id=%s sourceSHA256=%s compile=pass typed=pass allowed=%t actualCryptoExecuted=false", x.name, hashBytes([]byte(x.file+"\x00"+x.code)), x.allowed)
		})
	}
}
