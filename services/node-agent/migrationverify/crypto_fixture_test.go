package migrationverify

// This entire adapter is TEST-ONLY. It creates ephemeral keys/certificates in
// memory, regenerates every dependent signed object and reference, and supplies
// synthetic external registration/observation data. It is not a producer, live
// trust registration, imported real credential or acceptance of original dummies.

import (
	"crypto/ed25519"
	"crypto/rand"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"math/big"
	"net/url"
	"os"
	"strings"
	"testing"
	"time"
)

type cryptoFixture struct {
	installed InstalledTrust
	context   TrustedContext
	packet    Packet
	keys      map[string]ed25519.PrivateKey
}

func replaceStrings(v any, replacements map[string]string) any {
	switch x := v.(type) {
	case string:
		if s, ok := replacements[x]; ok {
			return s
		}
		return x
	case map[string]any:
		m := map[string]any{}
		for k, v := range x {
			m[k] = replaceStrings(v, replacements)
		}
		return m
	case []any:
		a := []any{}
		for _, v := range x {
			a = append(a, replaceStrings(v, replacements))
		}
		return a
	default:
		return v
	}
}
func setPointer(t *testing.T, v any, path string, value any) {
	t.Helper()
	i := strings.LastIndex(path, "/")
	if i < 0 {
		t.Fatal("bad set pointer")
	}
	parent, e := pointer(v, path[:i])
	if e != nil {
		t.Fatal(e)
	}
	key := strings.ReplaceAll(strings.ReplaceAll(path[i+1:], "~1", "/"), "~0", "~")
	switch p := parent.(type) {
	case map[string]any:
		p[key] = copyJSON(value)
	case []any:
		var n int
		if _, e = fmt.Sscan(key, &n); e != nil || n < 0 || n >= len(p) {
			t.Fatal("bad array set")
		}
		p[n] = copyJSON(value)
	default:
		t.Fatal("scalar set")
	}
}

// Graph rules deliberately omit proof references. Retain the containing proof
// locations while regenerating all non-proof values, then rebuild/authenticate
// those references in the separate proof layer below.
func retainProofLocations(old, next any) any {
	if isProof(old) {
		return copyJSON(old)
	}
	switch n := next.(type) {
	case map[string]any:
		out := copyJSON(n).(map[string]any)
		o, ok := old.(map[string]any)
		if !ok {
			return out
		}
		for k, v := range o {
			if isProof(v) {
				out[k] = copyJSON(v)
			} else if nv, ok := out[k]; ok {
				out[k] = retainProofLocations(v, nv)
			}
		}
		return out
	case []any:
		out := []any{}
		prior := []any{}
		proofs := []any{}
		if o, ok := old.([]any); ok {
			for _, v := range o {
				if isProof(v) {
					proofs = append(proofs, copyJSON(v))
				} else {
					prior = append(prior, v)
				}
			}
		}
		for _, v := range n {
			if isProof(v) {
				continue
			}
			i := len(out)
			if i < len(prior) {
				out = append(out, retainProofLocations(prior[i], v))
			} else {
				out = append(out, copyJSON(v))
			}
		}
		if len(proofs) == 0 {
			for _, v := range n {
				if isProof(v) {
					proofs = append(proofs, copyJSON(v))
				}
			}
		}
		out = append(out, proofs...)
		return out
	default:
		return next
	}
}

type proofMutation func(proofLocation, *proofContract, []byte, map[string]any, map[string]ed25519.PrivateKey, []KeyGrant) []byte
type cryptoFixtureOptions struct {
	IncludeOptionalProofs bool
	NativeLifetime        time.Duration
}

func newCryptoFixture(t *testing.T) *cryptoFixture { return newCryptoFixtureMutated(t, nil) }
func newCryptoFixtureMutated(t *testing.T, mutate proofMutation, options ...cryptoFixtureOptions) *cryptoFixture {
	t.Helper()
	v, p, _ := shapeRecipeVerifier(t)
	var option cryptoFixtureOptions
	if len(options) > 0 {
		option = options[0]
	}
	now := v.ctx.Now
	inputs := v.ctx.SemanticInputs.(map[string]any)
	origPolicy := fixture(t, "dummy-signer-policy.json").(map[string]any)
	roleKeys := origPolicy["roleKeys"].(map[string]any)
	replacement := map[string]string{}
	keys := map[string]ed25519.PrivateKey{}
	grants := []KeyGrant{}
	for name, x := range roleKeys {
		old := x.(string)
		pub, priv, e := ed25519.GenerateKey(rand.Reader)
		if e != nil {
			t.Fatal(e)
		}
		spki, e := publicSPKI(pub)
		if e != nil {
			t.Fatal(e)
		}
		replacement[old] = spki
		keys[spki] = priv
		parts := strings.SplitN(name, "@", 2)
		var authority any
		switch scope := parts[1]; {
		case scope == "COHORT":
			authority = v.cohortAuthority()
		case scope == "PC2" || scope == "PC4":
			m, e := v.member(scope)
			if e != nil {
				t.Fatal(e)
			}
			authority = nodeAuthority(m.Scope)
		default:
			authority = componentAuthority(strings.TrimPrefix(scope, "CODE:"))
		}
		grants = append(grants, KeyGrant{Role: parts[0], AuthorityScope: authority, PublicKeyHex: hex.EncodeToString(pub), NotBefore: now.Add(-24 * time.Hour), NotAfter: now.Add(24 * time.Hour), Status: "ACTIVE"})
	}
	for _, c := range v.contracts.byID {
		old, e := pointer(inputs, "/policy/contracts/"+c.kind)
		if e != nil {
			t.Fatal(e)
		}
		replacement[old.(string)] = c.hash
	}
	registryHash := shaHex([]byte("EPHEMERAL TEST external registry; no live provenance"))
	oldRegistry, _ := pointer(inputs, "/policy/allowedRegistrySHA256")
	replacement[oldRegistry.(string)] = registryHash
	// One explicit ephemeral test CA, with two scoped leaves. No private DER or
	// private key is written to disk, installed, or exposed in test output.
	caPub, caKey, e := ed25519.GenerateKey(rand.Reader)
	if e != nil {
		t.Fatal(e)
	}
	caTemplate := &x509.Certificate{SerialNumber: big.NewInt(900), Subject: pkix.Name{CommonName: "EPHEMERAL K1 TEST CA"}, NotBefore: now.Add(-time.Hour), NotAfter: now.Add(24 * time.Hour), IsCA: true, BasicConstraintsValid: true, KeyUsage: x509.KeyUsageCertSign | x509.KeyUsageCRLSign}
	caDER, e := x509.CreateCertificate(rand.Reader, caTemplate, caTemplate, caPub, caKey)
	if e != nil {
		t.Fatal(e)
	}
	for i := range v.trust.Members {
		m := &v.trust.Members[i]
		scope := m.Scope.(map[string]any)
		oldLeafKey, _ := pointer(inputs, "/policy/roles/node-leaf/"+m.Slot)
		priv := keys[replacement[oldLeafKey.(string)]]
		uri, e := url.Parse("spiffe://saintvision.ai/tenant/" + scope["tenantId"].(string) + "/node/" + scope["nodeId"].(string) + "/epoch/" + scope["recoveryEpoch"].(string))
		if e != nil {
			t.Fatal(e)
		}
		lifetime := 12 * time.Hour
		if option.NativeLifetime > 0 {
			lifetime = option.NativeLifetime
		}
		leaf := &x509.Certificate{SerialNumber: big.NewInt(int64(i + 1)), Subject: pkix.Name{CommonName: "EPHEMERAL TEST " + m.Slot}, NotBefore: now.Add(-time.Hour), NotAfter: now.Add(lifetime), BasicConstraintsValid: true, KeyUsage: x509.KeyUsageDigitalSignature, ExtKeyUsage: []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth}, URIs: []*url.URL{uri}}
		der, e := x509.CreateCertificate(rand.Reader, leaf, caTemplate, priv.Public(), caKey)
		if e != nil {
			t.Fatal(e)
		}
		m.CertificateDER = der
		m.CARootDER = caDER
		old, _ := pointer(inputs, fmt.Sprintf("/plan/memberInputs/%d/authority/nodeLeafDERSHA256", i))
		replacement[old.(string)] = shaHex(der)
	}
	inputs = replaceStrings(inputs, replacement).(map[string]any)
	for id, x := range p {
		p[id] = replaceStrings(x, replacement)
	}
	v.ctx.SemanticInputs = inputs
	if option.IncludeOptionalProofs {
		makeRef := func(id string) any {
			s := v.contracts.slots[id]
			return map[string]any{"slotId": id, "contractId": s.ContractID, "signatureDomainASCII": s.Domain, "producerRole": s.Producer, "signerRole": s.Role, "typedSubject": map[string]any{}}
		}
		body := p["event-36"].(map[string]any)["body"].(map[string]any)
		body["evidence"] = []any{makeRef("migration-event:/body/evidence/*")}
		body["memberStates"].([]any)[0].(map[string]any)["latestEvidence"] = []any{makeRef("migration-event:/body/memberStates/*/latestEvidence/*")}
	}
	v.ctx.Operations = map[string]OperationBinding{}
	v.ctx.Publications = map[string]PublicationStatus{}
	v.ctx.Certificates = map[string]CertificateStatus{}
	v.ctx.Challenges = map[string]NativeChallenge{}
	for _, m := range v.trust.Members {
		v.ctx.Certificates[shaHex(m.CertificateDER)] = CertificateStatus{"UNREVOKED", now, now.Add(time.Minute)}
	}
	for _, id := range []string{"lease-migration", "lease-restore"} {
		b := p[id].(map[string]any)["body"].(map[string]any)
		acq, _ := strictTime(b["acquiredAt"].(string))
		exp, _ := strictTime(b["expiresAt"].(string))
		epoch, _ := b["fenceEpoch"].(json.Number).Int64()
		op := OperationBinding{b["migrationId"].(string), b["operationId"].(string), shaHex([]byte("TEST initial pre-rebind " + id)), epoch, acq, exp}
		v.ctx.Operations[op.OperationID] = op
	}
	for _, m := range v.trust.Members {
		scopeHash, _ := canonicalHash(m.Scope)
		nonce, _ := pointer(inputs, "/facts/nodes/"+m.Slot+"/observerNonce")
		op := v.ctx.Operations[v.ctx.MigrationOperationID]
		v.ctx.Challenges[op.OperationID+"\x00"+scopeHash] = NativeChallenge{nonce.(string), op.MigrationID, op.OperationID, scopeHash, op.FenceEpoch, now.Add(-time.Second), now.Add(time.Minute)}
	}
	digests := map[string]string{}
	done := map[string]any{}
	referents := map[string][]byte{}
	// Actual signing keys exist only in this test function's private map.
	makeProof := func(loc proofLocation) {
		s, e := v.slot(loc, p[loc.node])
		if e != nil {
			t.Fatal(e)
		}
		c := v.contracts.byID[s.ContractID]
		subject, sources, e := v.subject(loc, p, digests, c)
		if e != nil {
			t.Fatalf("build %s%s: %v", loc.node, loc.path, e)
		}
		authority, e := v.proofAuthority(loc, subject)
		if e != nil {
			t.Fatal(e)
		}
		var grant KeyGrant
		for _, g := range grants {
			if g.Role == c.role && equal(g.AuthorityScope, authority) {
				if grant.Role != "" {
					t.Fatal("ambiguous TEST grant")
				}
				grant = g
			}
		}
		pub, _ := exactHex(grant.PublicKeyHex, 32)
		spki, _ := publicSPKI(pub)
		key := keys[spki]
		if len(key) == 0 {
			t.Fatal("missing TEST key")
		}
		observed := now
		until := now.Add(time.Minute)
		var op OperationBinding
		if c.mode == "fresh" {
			op, e = v.proofOperation(sources)
			if e != nil {
				t.Fatal(e)
			}
		} else if c.mode == "immutable-provenance" {
			observed = now.Add(-2 * time.Hour)
			until = now.Add(-time.Hour)
		} else {
			observed = now.Add(-3 * time.Hour)
		}
		var raw []byte
		if c.codec == "native-m2-v2" {
			sub := subject.(map[string]any)
			scope := sub["scope"].(map[string]any)
			for _, m := range v.trust.Members {
				if equal(m.Scope, scope) {
					cert, e := x509.ParseCertificate(m.CertificateDER)
					if e != nil {
						t.Fatal(e)
					}
					if cert.NotAfter.Before(until) {
						until = cert.NotAfter.Truncate(time.Second)
					}
				}
			}
			body := map[string]any{"schemaVersion": "saintvision-node-peer-policy-floor:2", "tenantId": scope["tenantId"], "nodeId": scope["nodeId"], "recoveryEpoch": scope["recoveryEpoch"], "certificateDER_SHA256": sub["certificateDERSHA256"], "observedAt": json.Number(fmt.Sprint(observed.Unix())), "plainServingProcess": true}
			for _, k := range []string{"nonce", "peerPolicyVersion", "peerPolicySHA256", "floorSHA256", "journalIdentitySHA256", "journalUID", "servingPID", "servingExecutableSHA256", "servingProcessSHA256"} {
				body[k] = sub[k]
			}
			b, e := CanonicalJSON(body)
			if e != nil {
				t.Fatal(e)
			}
			body["nodeSignature"] = hex.EncodeToString(ed25519.Sign(key, append([]byte(c.domain+"\x00"), b...)))
			raw, e = CanonicalJSON(body)
			if e != nil {
				t.Fatal(e)
			}
			raw = append(raw, '\n') // Native transport LF is part of raw artifact identity.
		} else {
			body := map[string]any{"schemaVersion": "saintvision-migration-proof-envelope:1", "contractId": c.id, "typedSubject": subject, "observedAt": observed.Format("2006-01-02T15:04:05Z"), "validUntil": until.Format("2006-01-02T15:04:05Z")}
			if c.mode == "fresh" {
				body["migrationId"] = op.MigrationID
				body["operationId"] = op.OperationID
			}
			signer := map[string]any{"role": c.role, "keySPKISHA256": spki}
			msg, e := normalizedMessage(c.domain, body, signer)
			if e != nil {
				t.Fatal(e)
			}
			signer["signatureHex"] = hex.EncodeToString(ed25519.Sign(key, msg))
			raw, e = CanonicalJSON(map[string]any{"body": body, "signer": signer})
			if e != nil {
				t.Fatal(e)
			}
		}
		sc, _ := canonicalHash(subject)
		r := loc.reference
		r["contractSHA256"] = c.hash
		r["scopeSHA256"] = sc
		r["typedSubject"] = subject
		r["signerKeySPKISHA256"] = spki
		r["observedAt"] = observed.Format("2006-01-02T15:04:05Z")
		r["validUntil"] = until.Format("2006-01-02T15:04:05Z")
		if mutate != nil {
			raw = mutate(loc, c, raw, r, keys, grants)
		}
		hash := shaHex(raw)
		r["artifactSHA256"] = hash
		referents[hash] = raw
		if c.mode != "fresh" {
			v.ctx.Publications[hash] = PublicationStatus{"ACCEPTED_UNREVOKED", sc, observed.Add(time.Second), now, now.Add(time.Minute)}
		}
		if c.kind == "inventory-head-readback" {
			sub := subject.(map[string]any)
			prefix := "migration"
			if strings.Contains(op.OperationID, "restore") {
				prefix = "restore"
			}
			inputs["verifiedReadbackIds"].(map[string]any)[prefix+"-"+strings.ToLower(sub["presence"].(string))] = hash
		}
	}
	for _, id := range v.graph.order {
		kind := v.trust.NodeKinds[id]
		done[id] = p[id]
		for _, r := range v.graph.rules[id] {
			value, e := evaluate(r.Expression, inputs, done, digests)
			if e != nil {
				t.Fatalf("regen %s%s: %v", id, r.Pointer, e)
			}
			old, e := pointer(p[id], r.Pointer)
			if e != nil {
				t.Fatal(e)
			}
			setPointer(t, p[id], r.Pointer, retainProofLocations(old, value))
		}
		if e := visitProofs(id, kind, p[id], func(loc proofLocation) error {
			if loc.reference["contractId"] == "saintvision-proof-independent-plan-review:1" || loc.reference["contractId"] == "saintvision-proof-root-publication-intent:1" {
				return nil
			}
			makeProof(loc)
			return nil
		}); e != nil {
			t.Fatal(e)
		}
		if id == "plan" {
			body := p[id].(map[string]any)["body"].(map[string]any)
			reduced := copyJSON(body).(map[string]any)
			for _, k := range []string{"planSubjectSHA256", "independentPlanReview", "rootPublicationIntent"} {
				delete(reduced, k)
			}
			h, _ := canonicalHash(reduced)
			body["planSubjectSHA256"] = h
			if e := visitProofs(id, kind, p[id], func(loc proofLocation) error {
				if loc.reference["contractId"] == "saintvision-proof-independent-plan-review:1" || loc.reference["contractId"] == "saintvision-proof-root-publication-intent:1" {
					makeProof(loc)
				}
				return nil
			}); e != nil {
				t.Fatal(e)
			}
			inputs["plan"] = copyJSON(body)
		}
		if domain, signed := outerDomains[kind]; signed {
			m := p[id].(map[string]any)
			signer := m["signer"].(map[string]any)
			key := keys[signer["keySPKISHA256"].(string)]
			b, e := CanonicalJSON(m["body"])
			if e != nil {
				t.Fatal(e)
			}
			signature := hex.EncodeToString(ed25519.Sign(key, append([]byte(domain+"\x00"), b...)))
			signer["signatureHex"] = signature
			assignments := inputs["dummySignerPolicy"].(map[string]any)["artifactAssignments"].(map[string]any)
			assignments[id].(map[string]any)["signatureHex"] = signature
		}
		d, e := ArtifactDigest(kind, p[id])
		if e != nil {
			t.Fatal(e)
		}
		digests[id] = d
		if kind == "runtime-inventory" {
			// The original scenario supplies the genuine post-publication readback
			// before the next request. Regenerate that producer receipt as soon as
			// the exact signed inventory digest exists, without inventing a proof
			// from the derived set or waiting for its dependent request.
			for rid, rp := range p {
				if v.trust.NodeKinds[rid] != "api-request" {
					continue
				}
				rm := rp.(map[string]any)
				head := rm["expectedInventoryHead"].(map[string]any)
				if head["presence"] != "PRESENT" {
					continue
				}
				head["envelopeSHA256"] = d
				makeProof(proofLocation{rid, "api-request", "/expectedInventoryHead/readbackProof", "/expectedInventoryHead/readbackProof", head["readbackProof"].(map[string]any)})
			}
		}
	}
	if _, e := v.graph.check(inputs, p, v.trust.NodeKinds); e != nil {
		t.Fatalf("fully regenerated REAL-CRYPTO TEST graph: %v", e)
	}
	for _, id := range []string{"lease-migration", "lease-restore"} {
		b := p[id].(map[string]any)["body"].(map[string]any)
		op := v.ctx.Operations[b["operationId"].(string)]
		op.LeaseEnvelopeSHA256 = digests[id]
		v.ctx.Operations[op.OperationID] = op
	}
	current := p["cohort-36"].(map[string]any)
	epoch, _ := current["fenceEpoch"].(json.Number).Int64()
	seq, _ := current["sequence"].(json.Number).Int64()
	members := current["members"].([]any)
	v.ctx.Current = &CurrentProjectionContext{SetID: "cohort-36", MigrationID: current["migrationId"].(string), OperationID: current["operationId"].(string), PlanEnvelopeSHA256: current["planEnvelopeSHA256"].(string), LeaseEnvelopeSHA256: current["leaseEnvelopeSHA256"].(string), FenceEpoch: epoch, Sequence: seq, InventoryHead: current["inventoryHead"], InventoryReadbackSHA256: current["inventoryHeadReadbackSHA256"].(string), MemberProjectionSHA256: []string{members[0].(map[string]any)["projectionEnvelopeSHA256"].(string), members[1].(map[string]any)["projectionEnvelopeSHA256"].(string)}}
	graphRaw, e := os.ReadFile("testdata/artifact-reference-graph.json")
	if e != nil {
		t.Fatal(e)
	}
	v.trust.RegistrySHA256 = registryHash
	v.trust.Verifier = VerifierPublication{"saintvision-migrationverify-k1:1", strings.Repeat("1", 40), shaHex([]byte("EPHEMERAL TEST verifier artifact provenance")), strings.Repeat("2", 40), []string{"EPHEMERAL TEST CI -- NOT REAL"}}
	v.trust.Grants = grants
	v.trust.ContractPins = map[string]ContractPin{}
	v.trust.GraphBytes = graphRaw
	v.trust.GraphSHA256 = shaHex(graphRaw)
	for id, c := range v.contracts.byID {
		v.trust.ContractPins[id] = ContractPin{c.hash, c.schemaHash, c.codec, c.verifier}
	}
	packet := Packet{Records: map[string][]byte{}, Referents: referents}
	for id, p := range p {
		b, e := CanonicalJSON(p)
		if e != nil {
			t.Fatal(e)
		}
		packet.Records[id] = b
	}
	return &cryptoFixture{v.trust, v.ctx, packet, keys}
}

func TestRegeneratedEphemeralCryptoPacketAndCurrentDerivedSet(t *testing.T) {
	f := newCryptoFixture(t)
	v, e := NewVerifier(f.installed, f.context)
	if e != nil {
		t.Fatal(e)
	}
	r, e := v.Verify(f.packet)
	if e != nil {
		t.Fatal(e)
	}
	if r.Records != 195 || r.ProofReferences != 112 || r.RealSignatures != 227 {
		t.Fatalf("counts %+v", r)
	}
	d, e := v.VerifyCurrentProjectionSet(f.packet, "cohort-36")
	if e != nil {
		t.Fatal(e)
	}
	if d != r.Digests["cohort-36"] {
		t.Fatal("current derived mismatch")
	}
	if _, e = v.VerifyCurrentProjectionSet(f.packet, "cohort-34"); e == nil {
		t.Fatal("released epoch1 substituted for current restore-held epoch2")
	}
	t.Log("EPHEMERAL TEST: 115 newly signed outer records +112 actually verified proof references; original dummy signatures verified=0; no live registration/effects")
}
