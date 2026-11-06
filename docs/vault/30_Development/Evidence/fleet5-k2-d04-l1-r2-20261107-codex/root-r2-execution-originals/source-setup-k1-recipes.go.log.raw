package migrationverify

import (
	"bytes"
	"errors"
	"fmt"
	"strconv"
	"strings"
)

type proofLocation struct {
	node, kind, path, normalized string
	reference                    map[string]any
}

func visitProofs(node, kind string, payload any, fn func(proofLocation) error) error {
	var walk func(any, string, string) error
	walk = func(v any, path, normalized string) error {
		if isProof(v) {
			return fn(proofLocation{node, kind, path, normalized, v.(map[string]any)})
		}
		switch x := v.(type) {
		case map[string]any:
			for k, v := range x {
				part := strings.ReplaceAll(strings.ReplaceAll(k, "~", "~0"), "/", "~1")
				if e := walk(v, path+"/"+part, normalized+"/"+part); e != nil {
					return e
				}
			}
		case []any:
			for i, v := range x {
				if e := walk(v, path+"/"+strconv.Itoa(i), normalized+"/*"); e != nil {
					return e
				}
			}
		}
		return nil
	}
	return walk(payload, "", "")
}

func (v *Verifier) slot(loc proofLocation, payload any) (proofSlot, error) {
	prefix := loc.kind
	if loc.kind == "api-request" {
		m, e := object(payload)
		if e != nil {
			return proofSlot{}, e
		}
		method, e := text(m["method"])
		if e != nil {
			return proofSlot{}, e
		}
		prefix += "[" + method + "]"
	}
	id := prefix + ":" + loc.normalized
	s, ok := v.contracts.slots[id]
	if !ok || loc.reference["slotId"] != id {
		return s, errors.New("proof not in exact containing slot/method")
	}
	return s, nil
}

// CanonicalArgvJSON is the distinct ordered raw-UTF8 JSON-array contract. Unlike
// C2 it does not HTML-escape or escape U+2028/2029. NUL is forbidden in argv.
func CanonicalArgvJSON(value any) ([]byte, error) {
	a, ok := value.([]any)
	if !ok {
		return nil, errors.New("argv is not an ordered array")
	}
	var b bytes.Buffer
	b.WriteByte('[')
	for i, x := range a {
		s, ok := x.(string)
		if !ok || strings.ContainsRune(s, 0) {
			return nil, errors.New("invalid argv string")
		}
		if e := validValue(s, 0); e != nil {
			return nil, e
		}
		if i > 0 {
			b.WriteByte(',')
		}
		b.WriteByte('"')
		for _, r := range s {
			switch r {
			case '"', '\\':
				b.WriteByte('\\')
				b.WriteRune(r)
			case '\b':
				b.WriteString(`\b`)
			case '\f':
				b.WriteString(`\f`)
			case '\n':
				b.WriteString(`\n`)
			case '\r':
				b.WriteString(`\r`)
			case '\t':
				b.WriteString(`\t`)
			default:
				if r < 0x20 {
					fmt.Fprintf(&b, `\u%04x`, r)
				} else {
					b.WriteRune(r)
				}
			}
		}
		b.WriteByte('"')
	}
	b.WriteByte(']')
	return b.Bytes(), nil
}

func recipeEval(expr any, sources map[string]any) (any, error) {
	m, e := object(expr)
	if e != nil || len(m) != 1 {
		return nil, errors.New("invalid recipe operator")
	}
	for op, a := range m {
		switch op {
		case "const":
			return a, nil
		case "get":
			x, e := object(a)
			if e != nil || len(x) != 2 {
				return nil, errors.New("invalid recipe get")
			}
			source, e := text(x["source"])
			if e != nil {
				return nil, e
			}
			p, e := text(x["pointer"])
			if e != nil {
				return nil, e
			}
			root, ok := sources[source]
			if !ok || root == nil {
				return nil, fmt.Errorf("missing authoritative recipe source %s", source)
			}
			return pointer(root, p)
		case "sha256C2":
			x, e := recipeEval(a, sources)
			if e != nil {
				return nil, e
			}
			return canonicalHash(x)
		case "sha256ArgvJSON":
			x, e := recipeEval(a, sources)
			if e != nil {
				return nil, e
			}
			b, e := CanonicalArgvJSON(x)
			if e != nil {
				return nil, e
			}
			return shaHex(b), nil
		default:
			return nil, errors.New("unknown subject recipe operator")
		}
	}
	return nil, errors.New("empty recipe")
}

func (v *Verifier) subject(loc proofLocation, payloads map[string]any, digests map[string]string, c *proofContract) (any, map[string]any, error) {
	sources, e := v.recipeSources(loc, payloads, digests)
	if e != nil {
		return nil, nil, e
	}
	r, e := object(v.contracts.recipes[c.kind])
	if e != nil {
		return nil, nil, e
	}
	out := map[string]any{"kind": c.kind}
	for k, expr := range r {
		x, e := recipeEval(expr, sources)
		if e != nil {
			return nil, nil, fmt.Errorf("%s %s: %w", loc.node, k, e)
		}
		out[k] = x
	}
	if e = c.subjectSchema.Validate(out); e != nil {
		return nil, nil, e
	}
	return out, sources, nil
}

func (v *Verifier) recipeSources(loc proofLocation, payloads map[string]any, digests map[string]string) (map[string]any, error) {
	plan, e := pointer(payloads["plan"], "/body")
	if e != nil {
		return nil, e
	}
	pm, e := object(plan)
	if e != nil {
		return nil, e
	}
	payload := payloads[loc.node]
	body := payload
	if loc.kind != "api-request" {
		if b, e := pointer(payload, "/body"); e == nil {
			body = b
		}
	}
	bm, e := object(body)
	if e != nil {
		return nil, e
	}
	inputs, e := object(v.ctx.SemanticInputs)
	if e != nil {
		return nil, e
	}
	facts, e := object(inputs["facts"])
	if e != nil {
		return nil, e
	}
	sources := map[string]any{"plan": plan, "body": body, "image": pm["image"], "facts": facts, "policy": inputs["policy"]}
	scopes := []any{}
	for _, m := range v.trust.Members {
		scopes = append(scopes, m.Scope)
	}
	scopeHash, e := canonicalHash(scopes)
	if e != nil {
		return nil, e
	}
	op, _ := bm["operationId"].(string)
	if op == "" {
		op = v.ctx.MigrationOperationID
	}
	aliases := map[string]any{"finalPlanEnvelopeSHA256": digests["plan"], "cohortScopesSHA256": scopeHash, "operationId": op}
	sources["aliases"] = aliases
	// Select the containing product, never the first product or first Node.
	components := map[string]string{"acceptedP0": "node-agent", "migrationHelper": "plain-migration-helper", "commonFence": "agent-mutation-fence", "runtimeInventoryAPI": "runtime-inventory-api", "schema3Helper": "schema3-helper", "newRenewalGuard": "renewal-guard", "target": "node-agent"}
	for field, component := range components {
		prefix := "/body/" + field + "/"
		if strings.HasPrefix(loc.path, prefix) {
			sources["product"] = bm[field]
			aliases["componentId"] = component
		}
	}
	if strings.HasSuffix(loc.path, "/attestation") {
		parent := strings.TrimSuffix(loc.path, "/attestation")
		if strings.HasSuffix(parent, "/coreCI") || strings.HasSuffix(parent, "/backendCI") {
			ci, e := pointer(payload, parent)
			if e != nil {
				return nil, e
			}
			sources["ci"] = ci
		}
	}
	if strings.HasSuffix(loc.path, "/readbackProof") {
		head, e := pointer(payload, strings.TrimSuffix(loc.path, "/readbackProof"))
		if e != nil {
			return nil, e
		}
		sources["head"] = head
	}
	var slot string
	var current any
	// Exact array member selection from the containing source.
	for _, prefix := range []string{"/body/members/", "/body/memberStates/"} {
		if strings.HasPrefix(loc.path, prefix) {
			rest := strings.TrimPrefix(loc.path, prefix)
			part := strings.Split(rest, "/")[0]
			parent, e := pointer(payload, strings.TrimSuffix(prefix, "/")+"/"+part)
			if e != nil {
				return nil, e
			}
			mm, e := object(parent)
			if e != nil {
				return nil, e
			}
			slot, _ = mm["slot"].(string)
			if prefix == "/body/members/" {
				current = parent
			} else {
				sources["progress"] = parent
			}
		}
	}
	if slot == "" {
		if s, ok := bm["slot"].(string); ok {
			slot = s
		}
	}
	if slot == "" {
		if args, ok := bm["arguments"].(map[string]any); ok {
			slot, _ = args["slot"].(string)
		}
	}
	if slot == "" {
		slot, _ = bm["targetSlot"].(string)
	}
	if slot != "" {
		member, e := v.member(slot)
		if e != nil {
			return nil, e
		}
		mi, ok := pm["memberInputs"].([]any)
		if !ok {
			return nil, errors.New("missing plan members")
		}
		var input map[string]any
		for _, x := range mi {
			m, e := object(x)
			if e != nil {
				return nil, e
			}
			if m["slot"] == slot {
				if input != nil {
					return nil, errors.New("duplicate plan member")
				}
				input = m
			}
		}
		if input == nil || !equal(input["scope"], member.Scope) {
			return nil, errors.New("containing member differs from external identity")
		}
		sources["input"] = input
		nf, e := pointer(facts, "/nodes/"+slot)
		if e != nil {
			return nil, e
		}
		sources["nodeFacts"] = nf
		if current == nil {
			cc, e := pointer(inputs, "/containers/"+slot+"/current")
			if e != nil {
				return nil, e
			}
			current = map[string]any{"currentContainer": cc, "volume": input["volume"]}
		}
		sources["current"] = current
		// A seal is selected by exact member scope, never a different member.
		for id, x := range payloads {
			if v.trust.NodeKinds[id] != "terminal-seal" {
				continue
			}
			sb, e := pointer(x, "/body")
			if e != nil {
				return nil, e
			}
			sm, e := object(sb)
			if e != nil {
				return nil, e
			}
			if sm["slot"] == slot && equal(sm["scope"], member.Scope) {
				if aliases["currentSealEnvelopeSHA256"] != nil {
					return nil, errors.New("ambiguous member seal")
				}
				aliases["currentSealEnvelopeSHA256"] = digests[id]
			}
		}
	}
	if effect, ok := bm["effect"].(map[string]any); ok && effect["kind"] != "none" {
		outcomes, e := object(facts["effectOutcomes"])
		if e != nil {
			return nil, errors.New("missing trusted effect outcome source")
		}
		seq, e := textNumber(bm["sequence"])
		if e != nil {
			return nil, e
		}
		aliases["observedEffectOutcome"] = outcomes[op+"|"+seq]
	}
	return sources, nil
}

func textNumber(v any) (string, error) {
	b, e := CanonicalJSON(v)
	if e != nil {
		return "", e
	}
	if !integerToken.Match(b) {
		return "", errors.New("expected exact integer")
	}
	return string(b), nil
}

func (v *Verifier) proofAuthority(loc proofLocation, subject any) (any, error) {
	s, e := object(subject)
	if e != nil {
		return nil, e
	}
	if scope, ok := s["scope"]; ok {
		for _, m := range v.trust.Members {
			if equal(scope, m.Scope) {
				return nodeAuthority(m.Scope), nil
			}
		}
		return nil, errors.New("proof scope is not registered")
	}
	if component, ok := s["component"].(string); ok {
		return componentAuthority(component), nil
	}
	if slot, ok := s["targetSlot"].(string); ok && slot != "" {
		m, e := v.member(slot)
		if e != nil {
			return nil, e
		}
		return nodeAuthority(m.Scope), nil
	}
	if s["kind"] == "migration-event-evidence" {
		b, e := pointer(v.ctx.SemanticInputs, "/facts/eventSlots/"+loc.node)
		if e != nil {
			return nil, e
		}
		if slot, ok := b.(string); ok && slot != "" {
			m, e := v.member(slot)
			if e != nil {
				return nil, e
			}
			return nodeAuthority(m.Scope), nil
		}
	}
	return v.cohortAuthority(), nil
}
