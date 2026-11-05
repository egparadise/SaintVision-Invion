package migrationverify

import (
	"crypto/ed25519"
	"crypto/x509"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"strings"
	"testing"
	"time"
)

func TestSemanticInputsRejectMalformedRequiredTimeWithoutPanic(t *testing.T) {
	f := newCryptoFixture(t)
	for name, change := range map[string]func(map[string]any){
		"nil-plan":       func(m map[string]any) { m["plan"] = nil },
		"missing-expiry": func(m map[string]any) { delete(m["plan"].(map[string]any), "expiresAt") },
		"number-expiry":  func(m map[string]any) { m["plan"].(map[string]any)["expiresAt"] = json.Number("1") },
		"nil-timing":     func(m map[string]any) { m["plan"].(map[string]any)["timing"] = nil },
		"string-age": func(m map[string]any) {
			m["plan"].(map[string]any)["timing"].(map[string]any)["maxEvidenceAgeSeconds"] = "120"
		},
		"nil-facts": func(m map[string]any) { m["facts"] = nil },
	} {
		t.Run(name, func(t *testing.T) {
			ctx := f.context
			ctx.SemanticInputs = copyJSON(ctx.SemanticInputs)
			change(ctx.SemanticInputs.(map[string]any))
			_, e := NewVerifier(f.installed, ctx)
			if e == nil || !strings.Contains(e.Error(), "SemanticInputs") {
				t.Fatalf("wrong malformed-input gate: %v", e)
			}
		})
	}
}

func TestNativeLeafRequiresExplicitSigningServerUsage(t *testing.T) {
	for name, opt := range map[string]cryptoFixtureOptions{
		"no-EKU":               {LeafUsageOverride: true, LeafKeyUsage: x509.KeyUsageDigitalSignature},
		"client-only":          {LeafUsageOverride: true, LeafKeyUsage: x509.KeyUsageDigitalSignature, LeafEKU: []x509.ExtKeyUsage{x509.ExtKeyUsageClientAuth}},
		"no-digital-signature": {LeafUsageOverride: true, LeafKeyUsage: x509.KeyUsageKeyEncipherment, LeafEKU: []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth}},
	} {
		t.Run(name, func(t *testing.T) {
			f := newCryptoFixtureMutated(t, nil, opt)
			v, e := NewVerifier(f.installed, f.context)
			if e != nil {
				t.Fatal(e)
			}
			_, e = v.Verify(f.packet)
			if e == nil || !strings.Contains(e.Error(), "explicit ServerAuth and DigitalSignature") {
				t.Fatalf("wrong leaf-usage gate: %v", e)
			}
		})
	}
}

func signedNativeAt(t *testing.T, f *cryptoFixture, raw []byte, observed time.Time, nonce string) []byte {
	t.Helper()
	value, e := ParseJSON(raw)
	if e != nil {
		t.Fatal(e)
	}
	m := value.(map[string]any)
	m["observedAt"] = json.Number(fmt.Sprint(observed.Unix()))
	if nonce != "" {
		m["nonce"] = nonce
	}
	delete(m, "nodeSignature")
	var key ed25519.PrivateKey
	for _, member := range f.installed.Members {
		scope := member.Scope.(map[string]any)
		if scope["nodeId"] == m["nodeId"] {
			cert, e := x509.ParseCertificate(member.CertificateDER)
			if e != nil {
				t.Fatal(e)
			}
			spki, _ := publicSPKI(cert.PublicKey.(ed25519.PublicKey))
			key = f.keys[spki]
		}
	}
	if key == nil {
		t.Fatal("missing TEST native signing key")
	}
	msg, e := CanonicalJSON(m)
	if e != nil {
		t.Fatal(e)
	}
	m["nodeSignature"] = hex.EncodeToString(ed25519.Sign(key, append([]byte("saintvision/node-peer-policy-floor/v2\x00"), msg...)))
	wire, e := CanonicalJSON(m)
	if e != nil {
		t.Fatal(e)
	}
	return append(wire, '\n')
}

func TestNativeSignedObservationChallengeWindow(t *testing.T) {
	f := newCryptoFixture(t)
	p := parsedPacket(t, f.packet)
	v, e := NewVerifier(f.installed, f.context)
	if e != nil {
		t.Fatal(e)
	}
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
	orig := f.packet.Referents[loc.reference["artifactSHA256"].(string)]
	for _, tc := range []struct {
		name  string
		delta time.Duration
		want  bool
	}{{"within-five-second-skew", -5 * time.Second, true}, {"exact-thirty-second-skew", -30 * time.Second, true}, {"before-skew", -31 * time.Second, false}, {"exact-expiry", 10 * time.Second, false}, {"after-expiry", 11 * time.Second, false}} {
		t.Run(tc.name, func(t *testing.T) {
			vv, e := NewVerifier(f.installed, f.context)
			if e != nil {
				t.Fatal(e)
			}
			for k, c := range vv.ctx.History.Challenges {
				c.IssuedAt = vv.ctx.Now
				c.ExpiresAt = vv.ctx.Now.Add(10 * time.Second)
				vv.ctx.History.Challenges[k] = c
			}
			obs := vv.ctx.Now.Add(tc.delta)
			raw := signedNativeAt(t, f, orig, obs, "")
			ref := copyJSON(loc.reference).(map[string]any)
			ref["observedAt"] = obs.Format(time.RFC3339)
			ref["artifactSHA256"] = shaHex(raw)
			l := loc
			l.reference = ref
			_, e = vv.verifyProof(l, p, d, map[string][]byte{shaHex(raw): raw})
			if tc.want && e != nil {
				t.Fatal(e)
			}
			if !tc.want && (e == nil || !strings.Contains(e.Error(), "matching operation challenge")) {
				t.Fatalf("wrong challenge-window gate: %v", e)
			}
		})
	}
}

func TestDurableHistoryBindingsAndNontransferableCurrentWitnesses(t *testing.T) {
	f := newCryptoFixtureMutated(t, nil, cryptoFixtureOptions{DurableHistory: true})
	for name, change := range map[string]func(*TrustedContext){
		"wrong-historical-lease": func(c *TrustedContext) {
			o := c.History.Operations[c.MigrationOperationID]
			o.LeaseEnvelopeSHA256 = strings.Repeat("f", 64)
			c.History.Operations[c.MigrationOperationID] = o
		},
		"wrong-historical-window": func(c *TrustedContext) {
			o := c.History.Operations[c.MigrationOperationID]
			o.AcquiredAt = o.AcquiredAt.Add(time.Second)
			c.History.Operations[c.MigrationOperationID] = o
		},
		"missing-historical-challenges": func(c *TrustedContext) { c.History.Challenges = nil },
	} {
		t.Run(name, func(t *testing.T) {
			v, e := NewVerifier(f.installed, f.context)
			if e != nil {
				t.Fatal(e)
			}
			change(&v.ctx)
			if _, e = v.Verify(f.packet); e == nil {
				t.Fatal("inconsistent historical binding accepted")
			}
		})
	}
	v, e := NewVerifier(f.installed, f.context)
	if e != nil {
		t.Fatal(e)
	}
	x, e := v.verify(f.packet)
	if e != nil {
		t.Fatal(e)
	}
	var old []byte
	for _, proof := range allLocations(t, v, x.payloads) {
		if proof.reference["contractId"] == "saintvision-proof-node-floor-v2:1" && equal(proof.reference["typedSubject"].(map[string]any)["scope"], f.installed.Members[0].Scope) {
			old = f.packet.Referents[proof.reference["artifactSHA256"].(string)]
			break
		}
	}
	for name, raw := range map[string][]byte{
		"old-retained":                  old,
		"old-time-relabelled-new-nonce": signedNativeAt(t, f, old, time.Date(2030, 1, 1, 0, 0, 32, 0, time.UTC), shaHex([]byte("EPHEMERAL TEST current nonce PC2"))),
		"wrong-current-nonce":           signedNativeAt(t, f, f.context.Current.NativeWitnesses[0].Raw, f.context.Now, strings.Repeat("f", 64)),
	} {
		t.Run(name, func(t *testing.T) {
			fresh, e := NewVerifier(f.installed, f.context)
			if e != nil {
				t.Fatal(e)
			}
			fresh.ctx.Current.NativeWitnesses[0].Raw = raw
			if e = fresh.currentNativeWitnesses(fresh.ctx.Current, x); e == nil {
				t.Fatal("historical/relabelled witness became current")
			}
		})
	}
	for k, g := range v.keys {
		if strings.HasPrefix(k, "node-leaf\x00") {
			g.after = time.Date(2030, 1, 1, 0, 2, 0, 0, time.UTC)
			v.keys[k] = g
		}
	}
	if _, e = v.Verify(f.packet); e != nil {
		t.Fatal("historical key interval incorrectly required at Now", e)
	}
	if e = v.currentNativeWitnesses(v.ctx.Current, x); e == nil {
		t.Fatal("historical key interval used for current witness")
	}
}

func TestPacketSnapshotSeversMapsAndByteSlices(t *testing.T) {
	f := newCryptoFixture(t)
	v, e := NewVerifier(f.installed, f.context)
	if e != nil {
		t.Fatal(e)
	}
	x, e := v.verify(f.packet)
	if e != nil {
		t.Fatal(e)
	}
	for hash, raw := range f.packet.Referents {
		old := append([]byte(nil), raw...)
		raw[0] ^= 1
		delete(f.packet.Referents, hash)
		if !equalBytes(x.referents[hash], old) {
			t.Fatal("authenticated referent aliases caller bytes/map")
		}
		break
	}
	f.packet.Records["plan"][0] ^= 1
	delete(f.packet.Records, "plan")
	if _, e = object(x.payloads["plan"]); e != nil {
		t.Fatal(e)
	}
	if _, e = v.Verify(f.packet); e == nil {
		t.Fatal("later mutated packet unexpectedly authenticated")
	}
}

func equalBytes(a, b []byte) bool { return string(a) == string(b) }

func TestDurableHistoricalSignedConsumingTimeControlsFreshness(t *testing.T) {
	f := newCryptoFixtureMutated(t, nil, cryptoFixtureOptions{DurableHistory: true, EventSeconds: map[string]int64{"inventory": 200}})
	v, e := NewVerifier(f.installed, f.context)
	if e != nil {
		t.Fatal(e)
	}
	_, e = v.Verify(f.packet)
	if e == nil || !strings.Contains(e.Error(), "inventory/body/") || !strings.Contains(e.Error(), "stale/future/expired") {
		t.Fatalf("wrong signed consuming-time gate: %v", e)
	}
}

func TestCurrentNativeExpiredAtNowAndContextCopy(t *testing.T) {
	f := newCryptoFixtureMutated(t, nil, cryptoFixtureOptions{DurableHistory: true})
	v, e := NewVerifier(f.installed, f.context)
	if e != nil {
		t.Fatal(e)
	}
	x, e := v.verify(f.packet)
	if e != nil {
		t.Fatal(e)
	}
	f.context.Current.NativeWitnesses[0].Raw[0] ^= 1
	if e = v.currentNativeWitnesses(v.ctx.Current, x); e != nil {
		t.Fatal("constructor aliases current witness bytes", e)
	}
	v.ctx.Now = v.ctx.Now.Add(121 * time.Second)
	for key, c := range v.ctx.Certificates {
		c.CheckedAt = v.ctx.Now
		c.ExpiresAt = v.ctx.Now.Add(time.Minute)
		v.ctx.Certificates[key] = c
	}
	for key, c := range v.ctx.Challenges {
		c.ExpiresAt = v.ctx.Now.Add(time.Minute)
		v.ctx.Challenges[key] = c
	}
	if e = v.currentNativeWitnesses(v.ctx.Current, x); e == nil || !strings.Contains(e.Error(), "stale/future/expired") {
		t.Fatalf("wrong expired current native gate: %v", e)
	}
}

func TestCurrentHeadReadbackRechecksKeyAtNow(t *testing.T) {
	f := newCryptoFixtureMutated(t, nil, cryptoFixtureOptions{DurableHistory: true})
	v, e := NewVerifier(f.installed, f.context)
	if e != nil {
		t.Fatal(e)
	}
	for key, g := range v.keys {
		if strings.HasPrefix(key, "cp-inventory\x00") {
			g.after = v.ctx.Now.Add(-5 * time.Second)
			v.keys[key] = g
		}
	}
	if _, e = v.Verify(f.packet); e != nil {
		t.Fatal("historical CP role interval rejected at Now", e)
	}
	_, e = v.VerifyCurrentProjectionSet(f.packet, "cohort-36")
	if e == nil || !strings.Contains(e.Error(), "current head readback lacks fresh current role") {
		t.Fatalf("wrong current CP role gate: %v", e)
	}
}

func TestCurrentLeaseAndChallengeBindingsAreExact(t *testing.T) {
	f := newCryptoFixtureMutated(t, nil, cryptoFixtureOptions{DurableHistory: true})
	for name, change := range map[string]func(*TrustedContext){
		"different-held-hash": func(c *TrustedContext) {
			o := c.Operations[c.Current.OperationID]
			o.LeaseEnvelopeSHA256 = c.History.Operations[c.MigrationOperationID].LeaseEnvelopeSHA256
			c.Operations[o.OperationID] = o
		},
		"different-held-window": func(c *TrustedContext) {
			o := c.Operations[c.Current.OperationID]
			o.AcquiredAt = o.AcquiredAt.Add(time.Second)
			c.Operations[o.OperationID] = o
		},
		"current-native-missing": func(c *TrustedContext) { c.Current.NativeWitnesses = nil },
		"current-native-member-order": func(c *TrustedContext) {
			c.Current.NativeWitnesses[0], c.Current.NativeWitnesses[1] = c.Current.NativeWitnesses[1], c.Current.NativeWitnesses[0]
		},
		"current-challenge-future": func(c *TrustedContext) {
			for k, ch := range c.Challenges {
				ch.IssuedAt = c.Now.Add(time.Second)
				c.Challenges[k] = ch
			}
		},
		"current-challenge-operation": func(c *TrustedContext) {
			for k, ch := range c.Challenges {
				ch.OperationID = c.MigrationOperationID
				c.Challenges[k] = ch
			}
		},
	} {
		t.Run(name, func(t *testing.T) {
			v, e := NewVerifier(f.installed, f.context)
			if e != nil {
				t.Fatal(e)
			}
			change(&v.ctx)
			_, e = v.VerifyCurrentProjectionSet(f.packet, "cohort-36")
			if e == nil {
				t.Fatal("inconsistent current lease/challenge accepted")
			}
		})
	}
}

func TestCurrentEpochSelectorIgnoresUnrelatedScopes(t *testing.T) {
	// Unit test of scoped epoch selection, after a genuinely authenticated packet.
	// The extra synthetic value is not claimed to be an authenticated packet.
	f := newCryptoFixtureMutated(t, nil, cryptoFixtureOptions{DurableHistory: true})
	v, e := NewVerifier(f.installed, f.context)
	if e != nil {
		t.Fatal(e)
	}
	x, e := v.verify(f.packet)
	if e != nil {
		t.Fatal(e)
	}
	foreign := copyJSON(x.payloads["lease-restore"]).(map[string]any)
	b := foreign["body"].(map[string]any)
	b["fenceEpoch"] = json.Number("999")
	scopes := b["scopes"].([]any)
	scopes[0].(map[string]any)["scope"].(map[string]any)["tenantId"] = "unrelated-tenant"
	x.payloads["selector-unit-foreign"] = foreign
	v.trust.NodeKinds["selector-unit-foreign"] = "operation-lease"
	if e = v.latestCurrent(x, v.ctx.Current); e != nil {
		t.Fatal("unrelated tenant fence compared", e)
	}
	b["scopes"] = copyJSON(x.payloads["lease-restore"].(map[string]any)["body"].(map[string]any)["scopes"])
	b["migrationId"] = "unrelated-migration"
	if e = v.latestCurrent(x, v.ctx.Current); e != nil {
		t.Fatal("unrelated migration fence compared", e)
	}
}
