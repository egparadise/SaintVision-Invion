package migrationverify

import (
	"encoding/json"
	"errors"
	"fmt"
	"sort"
	"strconv"
	"strings"
)

type graphRule struct {
	Node       string `json:"node"`
	Pointer    string `json:"pointer"`
	Expression any    `json:"expression"`
}
type graph struct {
	rules map[string][]graphRule
	order []string
}

func object(v any) (map[string]any, error) {
	m, ok := v.(map[string]any)
	if !ok {
		return nil, errors.New("expected object")
	}
	return m, nil
}
func text(v any) (string, error) {
	s, ok := v.(string)
	if !ok {
		return "", errors.New("expected string")
	}
	return s, nil
}
func equal(a, b any) bool {
	aa, e := CanonicalJSON(a)
	if e != nil {
		return false
	}
	bb, e := CanonicalJSON(b)
	return e == nil && string(aa) == string(bb)
}
func copyJSON(v any) any {
	b, e := CanonicalJSON(v)
	if e != nil {
		panic("internal non-JSON copy")
	}
	x, e := ParseJSON(b)
	if e != nil {
		panic(e)
	}
	return x
}

func pointer(v any, p string) (any, error) {
	if p == "" {
		return v, nil
	}
	if !strings.HasPrefix(p, "/") {
		return nil, errors.New("invalid JSON pointer")
	}
	for _, part := range strings.Split(p[1:], "/") {
		for i := 0; i < len(part); i++ {
			if part[i] == '~' {
				if i+1 >= len(part) || (part[i+1] != '0' && part[i+1] != '1') {
					return nil, errors.New("invalid pointer escape")
				}
				i++
			}
		}
		part = strings.ReplaceAll(strings.ReplaceAll(part, "~1", "/"), "~0", "~")
		switch x := v.(type) {
		case map[string]any:
			var ok bool
			v, ok = x[part]
			if !ok {
				return nil, fmt.Errorf("missing pointer %s", p)
			}
		case []any:
			i, e := strconv.Atoi(part)
			if e != nil || i < 0 || i >= len(x) || strconv.Itoa(i) != part {
				return nil, errors.New("invalid array pointer")
			}
			v = x[i]
		default:
			return nil, errors.New("pointer through scalar")
		}
	}
	return v, nil
}

func compileGraph(raw []byte, kinds map[string]string) (*graph, error) {
	v, e := ParseJSON(raw)
	if e != nil {
		return nil, e
	}
	m, e := object(v)
	if e != nil {
		return nil, e
	}
	rr, ok := m["rules"].([]any)
	if !ok {
		return nil, errors.New("missing graph rules")
	}
	g := &graph{rules: map[string][]graphRule{}}
	deps := map[string]map[string]bool{}
	seen := map[string]bool{}
	for _, x := range rr {
		x, e := object(x)
		if e != nil {
			return nil, e
		}
		node, e := text(x["node"])
		if e != nil {
			return nil, e
		}
		path, e := text(x["pointer"])
		if e != nil {
			return nil, e
		}
		r := graphRule{Node: node, Pointer: path, Expression: x["expression"]}
		if _, ok := kinds[r.Node]; !ok {
			return nil, errors.New("graph names unknown node")
		}
		key := r.Node + "\x00" + r.Pointer
		if seen[key] {
			return nil, errors.New("duplicate graph rule")
		}
		seen[key] = true
		if r.Pointer == "" || !strings.HasPrefix(r.Pointer, "/") {
			return nil, errors.New("invalid rule pointer")
		}
		if deps[r.Node] == nil {
			deps[r.Node] = map[string]bool{}
		}
		if e = expressionRefs(r.Expression, deps[r.Node], 0); e != nil {
			return nil, e
		}
		g.rules[r.Node] = append(g.rules[r.Node], r)
	}
	state := map[string]int{}
	var visit func(string) error
	visit = func(id string) error {
		if state[id] == 1 {
			return errors.New("cyclic graph")
		}
		if state[id] == 2 {
			return nil
		}
		if len(g.rules[id]) == 0 {
			return fmt.Errorf("missing graph node %s", id)
		}
		state[id] = 1
		ds := []string{}
		for d := range deps[id] {
			ds = append(ds, d)
		}
		sort.Strings(ds)
		for _, d := range ds {
			if e := visit(d); e != nil {
				return e
			}
		}
		state[id] = 2
		g.order = append(g.order, id)
		return nil
	}
	ids := []string{}
	for id := range kinds {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	for _, id := range ids {
		if e = visit(id); e != nil {
			return nil, e
		}
	}
	return g, nil
}

func expressionRefs(v any, refs map[string]bool, depth int) error {
	if depth > maxJSONDepth {
		return errors.New("expression depth")
	}
	m, e := object(v)
	if e != nil || len(m) != 1 {
		return errors.New("expression must have one operator")
	}
	for op, a := range m {
		switch op {
		case "const":
			return validValue(a, 0)
		case "input":
			_, e = text(a)
			return e
		case "digest":
			s, e := text(a)
			if e == nil {
				refs[s] = true
			}
			return e
		case "field":
			x, e := object(a)
			if e != nil || len(x) != 2 {
				return errors.New("invalid field expression")
			}
			s, e := text(x["node"])
			if e != nil {
				return e
			}
			if _, e = text(x["pointer"]); e != nil {
				return e
			}
			refs[s] = true
		case "planSubject":
			if a != "plan" {
				return errors.New("only fixed plan subject formula allowed")
			}
		case "canonicalSHA256":
			return expressionRefs(a, refs, depth+1)
		case "object":
			x, e := object(a)
			if e != nil {
				return e
			}
			for _, v := range x {
				if e = expressionRefs(v, refs, depth+1); e != nil {
					return e
				}
			}
		case "array", "add":
			x, ok := a.([]any)
			if !ok || op == "add" && len(x) == 0 {
				return errors.New("invalid expression operands")
			}
			for _, v := range x {
				if e = expressionRefs(v, refs, depth+1); e != nil {
					return e
				}
			}
		default:
			return errors.New("unknown expression operator")
		}
	}
	return nil
}

func evaluate(expr, inputs any, nodes map[string]any, digests map[string]string) (any, error) {
	m, _ := object(expr)
	for op, a := range m {
		switch op {
		case "const":
			return a, nil
		case "input":
			return pointer(inputs, a.(string))
		case "field":
			x := a.(map[string]any)
			n, ok := nodes[x["node"].(string)]
			if !ok {
				return nil, errors.New("unverified forward field")
			}
			return pointer(n, x["pointer"].(string))
		case "digest":
			s, ok := digests[a.(string)]
			if !ok {
				return nil, errors.New("unverified forward digest")
			}
			return s, nil
		case "object":
			out := map[string]any{}
			for k, x := range a.(map[string]any) {
				v, e := evaluate(x, inputs, nodes, digests)
				if e != nil {
					return nil, e
				}
				out[k] = v
			}
			return out, nil
		case "array":
			out := []any{}
			for _, x := range a.([]any) {
				v, e := evaluate(x, inputs, nodes, digests)
				if e != nil {
					return nil, e
				}
				out = append(out, v)
			}
			return out, nil
		case "add":
			var sum int64
			for _, x := range a.([]any) {
				v, e := evaluate(x, inputs, nodes, digests)
				if e != nil {
					return nil, e
				}
				n, ok := v.(json.Number)
				if !ok {
					return nil, errors.New("non-integer addition")
				}
				i, e := n.Int64()
				if e != nil || i > maxSafeInteger || i < -maxSafeInteger {
					return nil, errors.New("invalid add operand")
				}
				sum += i
				if sum > maxSafeInteger || sum < -maxSafeInteger {
					return nil, errors.New("unsafe sum")
				}
			}
			return json.Number(strconv.FormatInt(sum, 10)), nil
		case "canonicalSHA256":
			v, e := evaluate(a, inputs, nodes, digests)
			if e != nil {
				return nil, e
			}
			return canonicalHash(v)
		case "planSubject":
			n, ok := nodes["plan"]
			if !ok {
				return nil, errors.New("missing plan subject")
			}
			body, e := pointer(n, "/body")
			if e != nil {
				return nil, e
			}
			b := copyJSON(body).(map[string]any)
			for _, k := range []string{"planSubjectSHA256", "independentPlanReview", "rootPublicationIntent"} {
				delete(b, k)
			}
			return canonicalHash(b)
		}
	}
	return nil, errors.New("invalid expression")
}

func isProof(v any) bool {
	m, ok := v.(map[string]any)
	if !ok {
		return false
	}
	_, ok = m["slotId"]
	return ok && m["typedSubject"] != nil && m["contractId"] != nil
}
func stripProofs(v any) any {
	switch x := v.(type) {
	case map[string]any:
		m := map[string]any{}
		for k, v := range x {
			if !isProof(v) {
				m[k] = stripProofs(v)
			}
		}
		return m
	case []any:
		a := []any{}
		for _, v := range x {
			if !isProof(v) {
				a = append(a, stripProofs(v))
			}
		}
		return a
	default:
		return v
	}
}

// Graph comparisons occur only after closed artifact schemas validated every
// proof shape. Separate role/key/recipe/authentication is mandatory afterward.
func (g *graph) check(inputs any, payloads map[string]any, kinds map[string]string) (map[string]string, error) {
	digests := map[string]string{}
	done := map[string]any{}
	if len(payloads) != len(g.rules) {
		return nil, errors.New("incomplete or extra node set")
	}
	for _, id := range g.order {
		n, ok := payloads[id]
		if !ok {
			return nil, errors.New("missing graph payload")
		}
		// The sole self formula reads the reduced plan. Other self dependencies
		// are rejected by compileGraph as cycles.
		done[id] = n
		for _, r := range g.rules[id] {
			got, e := pointer(n, r.Pointer)
			if e != nil {
				return nil, e
			}
			want, e := evaluate(r.Expression, inputs, done, digests)
			if e != nil {
				return nil, e
			}
			if !equal(stripProofs(got), stripProofs(want)) {
				return nil, fmt.Errorf("binding mismatch %s%s", id, r.Pointer)
			}
		}
		if e := g.coverage(id, n); e != nil {
			return nil, e
		}
		d, e := ArtifactDigest(kinds[id], n)
		if e != nil {
			return nil, e
		}
		digests[id] = d
	}
	return digests, nil
}

func (g *graph) coverage(id string, v any) error {
	var walk func(any, string) error
	walk = func(v any, p string) error {
		if isProof(v) {
			return nil
		}
		switch x := v.(type) {
		case map[string]any:
			if len(x) > 0 {
				for k, v := range x {
					if e := walk(v, p+"/"+strings.ReplaceAll(strings.ReplaceAll(k, "~", "~0"), "/", "~1")); e != nil {
						return e
					}
				}
				return nil
			}
		case []any:
			if len(x) > 0 {
				for i, v := range x {
					if e := walk(v, p+"/"+strconv.Itoa(i)); e != nil {
						return e
					}
				}
				return nil
			}
		}
		count := 0
		for _, r := range g.rules[id] {
			if p == r.Pointer || strings.HasPrefix(p, r.Pointer+"/") {
				count++
			}
		}
		if count != 1 {
			return fmt.Errorf("non-proof leaf coverage %s%s = %d", id, p, count)
		}
		return nil
	}
	return walk(v, "")
}
