package migrationverify

import (
	"crypto/ed25519"
	"encoding/hex"
	"sort"
	"strings"
	"testing"
	"time"
)

func parsedPacket(t *testing.T, p Packet) map[string]any {
	t.Helper()
	out := map[string]any{}
	for id, b := range p.Records {
		v, e := ParseJSON(b)
		if e != nil {
			t.Fatal(e)
		}
		out[id] = v
	}
	return out
}
func clonePacket(p Packet) Packet {
	q := Packet{Records: map[string][]byte{}, Referents: map[string][]byte{}}
	for k, b := range p.Records {
		q.Records[k] = append([]byte(nil), b...)
	}
	for k, b := range p.Referents {
		q.Referents[k] = append([]byte(nil), b...)
	}
	return q
}
func allLocations(t *testing.T, v *Verifier, p map[string]any) []proofLocation {
	t.Helper()
	out := []proofLocation{}
	for id, x := range p {
		if e := visitProofs(id, v.trust.NodeKinds[id], x, func(loc proofLocation) error { out = append(out, loc); return nil }); e != nil {
			t.Fatal(e)
		}
	}
	return out
}

func TestExternalTrustIsRequiredAndNeverSelectedByPacket(t *testing.T) {
	for _, v := range []*Verifier{nil, {}} {
		if _, e := v.Verify(Packet{}); e == nil {
			t.Fatal("zero-state verifier accepted packet")
		}
		if _, e := v.AuthenticateNativeHistory([]byte(`{}`), "PC2"); e == nil {
			t.Fatal("zero-state verifier accepted native history")
		}
	}
	f := newCryptoFixture(t)
	for name, mutate := range map[string]func(*InstalledTrust){
		"missing-registry":        func(x *InstalledTrust) { x.RegistrySHA256 = "" },
		"missing-verifier-review": func(x *InstalledTrust) { x.Verifier.ReviewSHA = "" },
		"wrong-verifier":          func(x *InstalledTrust) { x.Verifier.ID = "caller-plugin" },
		"missing-contracts":       func(x *InstalledTrust) { x.ContractPins = nil },
		"no-keys":                 func(x *InstalledTrust) { x.Grants = nil },
		"revoked-key": func(x *InstalledTrust) {
			x.Grants = append([]KeyGrant(nil), x.Grants...)
			x.Grants[0].Status = "REVOKED"
		},
		"wrong-graph":    func(x *InstalledTrust) { x.GraphSHA256 = strings.Repeat("f", 64) },
		"missing-member": func(x *InstalledTrust) { x.Members = x.Members[:1] },
		"member-order": func(x *InstalledTrust) {
			x.Members = append([]MemberIdentity(nil), x.Members...)
			x.Members[0], x.Members[1] = x.Members[1], x.Members[0]
		},
	} {
		t.Run(name, func(t *testing.T) {
			x := f.installed
			mutate(&x)
			if _, e := NewVerifier(x, f.context); e == nil {
				t.Fatal("untrusted registration accepted")
			}
		})
	}
	for name, pin := range map[string]ContractPin{
		"null-contract": {}, "unknown-codec": {strings.Repeat("a", 64), strings.Repeat("b", 64), "caller-codec", "caller-verifier"},
	} {
		t.Run(name, func(t *testing.T) {
			x := f.installed
			x.ContractPins = map[string]ContractPin{}
			for k, v := range f.installed.ContractPins {
				x.ContractPins[k] = v
			}
			for k := range x.ContractPins {
				x.ContractPins[k] = pin
				break
			}
			if _, e := NewVerifier(x, f.context); e == nil {
				t.Fatal("bad contract pin accepted")
			}
		})
	}
	v, e := NewVerifier(f.installed, f.context)
	if e != nil {
		t.Fatal(e)
	}
	if _, e = v.Verify(Packet{}); e == nil {
		t.Fatal("supplied digest alone accepted")
	}
	original := fixture(t, "scenario-objects.json").(map[string]any)["nodes"].(map[string]any)
	packet := Packet{Records: map[string][]byte{}, Referents: map[string][]byte{}}
	for id, x := range original {
		b, e := CanonicalJSON(x.(map[string]any)["payload"])
		if e != nil {
			t.Fatal(e)
		}
		packet.Records[id] = b
	}
	if _, e = v.Verify(packet); e == nil {
		t.Fatal("original dummy signatures accepted as real crypto")
	}
}

func TestRealSignedWrongScopedKeyFullDependentRebind(t *testing.T) {
	// Three complete independently regenerated packets exercise Node, cohort and
	// component authorities. Every digest, final plan approval and outer signature
	// is rebound after the attack; graph success cannot mask the scoped key check.
	for _, target := range []string{"node-floor-v2", "build-provenance", "inventory-head-readback"} {
		t.Run(target, func(t *testing.T) {
			changed := 0
			f := newCryptoFixtureMutated(t, func(loc proofLocation, c *proofContract, raw []byte, ref map[string]any, keys map[string]ed25519.PrivateKey, grants []KeyGrant) []byte {
				if c.kind != target {
					return raw
				}
				changed++
				// Use a real different key: the signature is deliberately VALID under
				// that key but its registered authority is not this role@scope.
				var wrong string
				for _, g := range grants {
					if g.Role != c.role {
						continue
					}
					pub, _ := exactHex(g.PublicKeyHex, 32)
					spki, _ := publicSPKI(pub)
					if spki != ref["signerKeySPKISHA256"] {
						wrong = spki
						break
					}
				}
				if wrong == "" {
					ordered := []string{}
					for h := range keys {
						ordered = append(ordered, h)
					}
					sort.Strings(ordered)
					for _, h := range ordered {
						if h != ref["signerKeySPKISHA256"] {
							wrong = h
							break
						}
					}
				}
				value, e := ParseJSON(raw)
				if e != nil {
					t.Fatal(e)
				}
				m := value.(map[string]any)
				if c.codec == "native-m2-v2" {
					delete(m, "nodeSignature")
					b, e := CanonicalJSON(m)
					if e != nil {
						t.Fatal(e)
					}
					sig := ed25519.Sign(keys[wrong], append([]byte(c.domain+"\x00"), b...))
					if e = verifyEd25519(keys[wrong].Public().(ed25519.PublicKey), append([]byte(c.domain+"\x00"), b...), sig); e != nil {
						t.Fatal(e)
					}
					m["nodeSignature"] = hex.EncodeToString(sig)
				} else {
					body := m["body"].(map[string]any)
					signer := m["signer"].(map[string]any)
					signer["keySPKISHA256"] = wrong
					msg, e := normalizedMessage(c.domain, body, signer)
					if e != nil {
						t.Fatal(e)
					}
					sig := ed25519.Sign(keys[wrong], msg)
					if e = verifyEd25519(keys[wrong].Public().(ed25519.PublicKey), msg, sig); e != nil {
						t.Fatal(e)
					}
					signer["signatureHex"] = hex.EncodeToString(sig)
				}
				ref["signerKeySPKISHA256"] = wrong
				b, e := CanonicalJSON(m)
				if e != nil {
					t.Fatal(e)
				}
				return b
			})
			if changed == 0 {
				t.Fatal("attack did not reach target")
			}
			v, e := NewVerifier(f.installed, f.context)
			if e != nil {
				t.Fatal(e)
			}
			if _, e = v.Verify(f.packet); e == nil {
				t.Fatal("real signed wrong authority accepted")
			}
		})
	}
}

func TestEveryProofKeyAndSubjectIndependentOfGraph(t *testing.T) {
	f := newCryptoFixture(t)
	v, e := NewVerifier(f.installed, f.context)
	if e != nil {
		t.Fatal(e)
	}
	p := parsedPacket(t, f.packet)
	d, e := v.graph.check(v.ctx.SemanticInputs, p, v.trust.NodeKinds)
	if e != nil {
		t.Fatal(e)
	}
	count := 0
	for _, loc := range allLocations(t, v, p) {
		original := loc.reference["signerKeySPKISHA256"]
		loc.reference["signerKeySPKISHA256"] = strings.Repeat("f", 64)
		if _, e = v.verifyProof(loc, p, d, f.packet.Referents); e == nil {
			t.Fatalf("unregistered key %s%s", loc.node, loc.path)
		}
		loc.reference["signerKeySPKISHA256"] = original
		sub := loc.reference["typedSubject"].(map[string]any)
		oldKind := sub["kind"]
		sub["kind"] = "foreign-kind"
		scope, _ := canonicalHash(sub)
		oldScope := loc.reference["scopeSHA256"]
		loc.reference["scopeSHA256"] = scope
		if _, e = v.verifyProof(loc, p, d, f.packet.Referents); e == nil {
			t.Fatalf("rehashed foreign subject %s%s", loc.node, loc.path)
		}
		sub["kind"] = oldKind
		loc.reference["scopeSHA256"] = oldScope
		count++
	}
	if count != 112 {
		t.Fatal(count)
	}
	for _, loc := range allLocations(t, v, p) {
		c := v.contracts.byID[loc.reference["contractId"].(string)]
		if c.kind != "node-floor-v2" && c.kind != "independent-code-review" {
			continue
		}
		_, sources, e := v.subject(loc, p, d, c)
		if e != nil {
			t.Fatal(e)
		}
		var authority map[string]any
		var field string
		if c.kind == "node-floor-v2" {
			x, e := pointer(sources["input"], "/authority")
			if e != nil {
				t.Fatal(e)
			}
			authority = x.(map[string]any)
			field = "nodeKeyPublicSPKISHA256"
		} else {
			x, e := pointer(sources["product"], "/independentReview")
			if e != nil {
				t.Fatal(e)
			}
			authority = x.(map[string]any)
			field = "reviewerKeySPKISHA256"
		}
		old := authority[field]
		authority[field] = strings.Repeat("e", 64)
		if _, e = v.verifyProof(loc, p, d, f.packet.Referents); e == nil {
			t.Fatal("containing Node/reviewer key ignored")
		}
		authority[field] = old
	}
}

func TestNormalizedWireSignatureFreshnessAndPublicationNegatives(t *testing.T) {
	f := newCryptoFixture(t)
	v, e := NewVerifier(f.installed, f.context)
	if e != nil {
		t.Fatal(e)
	}
	p := parsedPacket(t, f.packet)
	d, e := v.graph.check(v.ctx.SemanticInputs, p, v.trust.NodeKinds)
	if e != nil {
		t.Fatal(e)
	}
	locations := allLocations(t, v, p)
	byMode := map[string]proofLocation{}
	for _, loc := range locations {
		c := v.contracts.byID[loc.reference["contractId"].(string)]
		if c.codec == "normalized-proof-v1" {
			byMode[c.mode] = loc
		}
	}
	for mode, loc := range byMode {
		t.Run(mode, func(t *testing.T) {
			if _, e = v.verifyProof(loc, p, d, f.packet.Referents); e != nil {
				t.Fatal(e)
			}
			for _, attack := range []string{"tampered-signature", "role-with-reused-key", "spki-with-reused-key", "extra-field", "whitespace", "lf", "wrong-contract", "wrong-operation", "expired", "future", "future-publication", "noncanonical-time"} {
				t.Run(attack, func(t *testing.T) {
					ref := copyJSON(loc.reference).(map[string]any)
					l := loc
					l.reference = ref
					oldHash := ref["artifactSHA256"].(string)
					raw := append([]byte(nil), f.packet.Referents[oldHash]...)
					value, e := ParseJSON(raw)
					if e != nil {
						t.Fatal(e)
					}
					m := value.(map[string]any)
					body := m["body"].(map[string]any)
					signer := m["signer"].(map[string]any)
					key := f.keys[signer["keySPKISHA256"].(string)]
					switch attack {
					case "role-with-reused-key":
						signer["role"] = "root-fence"
					case "spki-with-reused-key":
						signer["keySPKISHA256"] = strings.Repeat("f", 64)
						ref["signerKeySPKISHA256"] = signer["keySPKISHA256"]
					case "extra-field":
						body["grant"] = true
					case "wrong-contract":
						body["contractId"] = "foreign-contract:1"
					case "wrong-operation":
						body["operationId"] = "foreign-current-operation"
					case "expired":
						originalObserved, _ := strictTime(body["observedAt"].(string))
						body["validUntil"] = originalObserved.Add(-time.Second).Format("2006-01-02T15:04:05Z")
						ref["validUntil"] = body["validUntil"]
					case "future":
						body["observedAt"] = v.ctx.Now.Add(time.Hour).Format("2006-01-02T15:04:05Z")
						ref["observedAt"] = body["observedAt"]
					case "noncanonical-time":
						body["observedAt"] = "2030-01-01T00:00:00+00:00"
						ref["observedAt"] = body["observedAt"]
					case "future-publication":
						body["observedAt"] = v.ctx.Now.Add(time.Hour).Format("2006-01-02T15:04:05Z")
						body["validUntil"] = v.ctx.Now.Add(2 * time.Hour).Format("2006-01-02T15:04:05Z")
						ref["observedAt"] = body["observedAt"]
						ref["validUntil"] = body["validUntil"]
					}
					c := v.contracts.byID[loc.reference["contractId"].(string)]
					msg, e := normalizedMessage(c.domain, body, signer)
					if e != nil {
						t.Fatal(e)
					}
					signer["signatureHex"] = hex.EncodeToString(ed25519.Sign(key, msg))
					if attack == "tampered-signature" {
						sig, _ := hex.DecodeString(signer["signatureHex"].(string))
						sig[0] ^= 1
						signer["signatureHex"] = hex.EncodeToString(sig)
					}
					raw, e = CanonicalJSON(m)
					if e != nil {
						t.Fatal(e)
					}
					if attack == "whitespace" {
						raw = append([]byte(" "), raw...)
					}
					if attack == "lf" {
						raw = append(raw, '\n')
					}
					hash := shaHex(raw)
					ref["artifactSHA256"] = hash
					refs := map[string][]byte{hash: raw}
					if old, ok := v.ctx.Publications[oldHash]; ok {
						if attack == "future-publication" {
							old.PublishedAt = v.ctx.Now.Add(time.Hour + time.Second)
						}
						v.ctx.Publications[hash] = old
						defer delete(v.ctx.Publications, hash)
					}
					if _, e = v.verifyProof(l, p, d, refs); e == nil {
						t.Fatal("malicious real-signed proof accepted")
					}
				})
			}
		})
	}
	for mode, loc := range byMode {
		if mode == "fresh" {
			continue
		}
		hash := loc.reference["artifactSHA256"].(string)
		original := v.ctx.Publications[hash]
		for _, status := range []string{"", "REVOKED", "UNKNOWN"} {
			bad := original
			bad.Status = status
			v.ctx.Publications[hash] = bad
			if _, e = v.verifyProof(loc, p, d, f.packet.Referents); e == nil {
				t.Fatal("unaccepted publication")
			}
		}
		delete(v.ctx.Publications, hash)
		if _, e = v.verifyProof(loc, p, d, f.packet.Referents); e == nil {
			t.Fatal("missing publication")
		}
		v.ctx.Publications[hash] = original
		// A currently active grant cannot authenticate an archival signature from
		// before its actual role/scope authorization interval.
		for id, key := range v.keys {
			if strings.HasSuffix(id, "\x00"+loc.reference["signerKeySPKISHA256"].(string)) {
				saved := key
				key.before = v.ctx.Now.Add(-time.Hour)
				v.keys[id] = key
				if _, e = v.verifyProof(loc, p, d, f.packet.Referents); e == nil {
					t.Fatal("signature predates scoped key authorization")
				}
				v.keys[id] = saved
			}
		}
	}
}

func TestNativeM2ExactOriginalWireAndDerivedValidity(t *testing.T) {
	f := newCryptoFixture(t)
	v, e := NewVerifier(f.installed, f.context)
	if e != nil {
		t.Fatal(e)
	}
	p := parsedPacket(t, f.packet)
	d, e := v.graph.check(v.ctx.SemanticInputs, p, v.trust.NodeKinds)
	if e != nil {
		t.Fatal(e)
	}
	var loc proofLocation
	for _, l := range allLocations(t, v, p) {
		if l.reference["contractId"] == "saintvision-proof-node-floor-v2:1" {
			loc = l
			break
		}
	}
	if _, e = v.verifyProof(loc, p, d, f.packet.Referents); e != nil {
		t.Fatal(e)
	}
	hash := loc.reference["artifactSHA256"].(string)
	raw := f.packet.Referents[hash]
	if len(raw) == 0 || raw[len(raw)-1] != '\n' {
		t.Fatal("native LF identity not tested")
	}
	for _, attack := range []string{"signature", "signed-nonce", "signed-cert", "raw-c2-hash-substitution", "derived-expiry", "native-as-normalized"} {
		t.Run(attack, func(t *testing.T) {
			ref := copyJSON(loc.reference).(map[string]any)
			l := loc
			l.reference = ref
			value, e := ParseJSON(raw)
			if e != nil {
				t.Fatal(e)
			}
			m := value.(map[string]any)
			switch attack {
			case "signature":
				m["nodeSignature"] = strings.Repeat("0", 128)
			case "signed-nonce":
				m["nonce"] = strings.Repeat("e", 64)
			case "signed-cert":
				m["certificateDER_SHA256"] = strings.Repeat("e", 64)
			case "derived-expiry":
				ref["validUntil"] = "2030-01-01T00:02:00Z"
			case "native-as-normalized":
				m = map[string]any{"body": m, "signer": map[string]any{"role": "node-leaf"}}
			}
			b, e := CanonicalJSON(m)
			if e != nil {
				t.Fatal(e)
			}
			newHash := shaHex(b)
			refs := map[string][]byte{newHash: b}
			ref["artifactSHA256"] = newHash
			if attack == "raw-c2-hash-substitution" {
				refs = map[string][]byte{newHash: raw}
			}
			if _, e = v.verifyProof(l, p, d, refs); e == nil {
				t.Fatal("native negative accepted")
			}
		})
	}
	// Independent current challenge/certificate/lease state is mandatory even
	// when native bytes and signature are unchanged and valid.
	for name, mutate := range map[string]func(){
		"missing-challenge":        func() { v.ctx.Challenges = nil },
		"missing-revocation-state": func() { v.ctx.Certificates = nil },
		"wrong-operation":          func() { v.ctx.Operations = nil },
		"expired-operation": func() {
			for k, o := range v.ctx.Operations {
				o.ExpiresAt = v.ctx.Now.Add(-time.Second)
				v.ctx.Operations[k] = o
			}
		},
	} {
		t.Run(name, func(t *testing.T) {
			orig := v.ctx
			ops := map[string]OperationBinding{}
			for k, o := range orig.Operations {
				ops[k] = o
			}
			v.ctx.Operations = ops
			mutate()
			if _, e = v.verifyProof(loc, p, d, f.packet.Referents); e == nil {
				t.Fatal("missing native current context")
			}
			v.ctx = orig
		})
	}
}

func TestCallerMutationsCannotChangeInstalledVerifier(t *testing.T) {
	f := newCryptoFixture(t)
	v, e := NewVerifier(f.installed, f.context)
	if e != nil {
		t.Fatal(e)
	}
	f.installed.GraphBytes[0] = '!'
	for k := range f.installed.NodeKinds {
		delete(f.installed.NodeKinds, k)
		break
	}
	f.context.SemanticInputs.(map[string]any)["plan"] = nil
	if _, e = v.Verify(f.packet); e != nil {
		t.Fatal("constructor retained caller mutable state", e)
	}
}
