package migrationverify

import (
	"strings"
	"testing"
	"time"
)

func TestHistoricalNativeIsTypedAndCannotBecomeCurrentProof(t *testing.T) {
	f := newCryptoFixture(t)
	p := parsedPacket(t, f.packet)
	var raw []byte
	var slot string
	for _, loc := range allLocations(t, &Verifier{trust: f.installed}, p) {
		if loc.reference["contractId"] != "saintvision-proof-node-floor-v2:1" {
			continue
		}
		raw = f.packet.Referents[loc.reference["artifactSHA256"].(string)]
		scope := loc.reference["typedSubject"].(map[string]any)["scope"]
		for _, m := range f.installed.Members {
			if equal(scope, m.Scope) {
				slot = m.Slot
			}
		}
		break
	}
	f.context.Now = f.context.Now.Add(13 * time.Hour) // Explicit TEST time: original leaf expired.
	f.context.Operations = nil
	f.context.Challenges = nil
	for hash, status := range f.context.Certificates {
		status.CheckedAt = f.context.Now
		status.ExpiresAt = f.context.Now.Add(time.Minute)
		f.context.Certificates[hash] = status
	}
	v, e := NewVerifier(f.installed, f.context)
	if e != nil {
		t.Fatal(e)
	}
	h, e := v.AuthenticateNativeHistory(raw, slot)
	if e != nil {
		t.Fatal(e)
	}
	if h.Classification != "AUTHENTICATED_ORIGINAL_NATIVE_HISTORY_NOT_FRESH_PROOF" || h.ExactReferentSHA256 != shaHex(raw) {
		t.Fatal("wrong historical type/bytes")
	}
	if _, e = v.Verify(f.packet); e == nil {
		t.Fatal("historical M2 substituted for current operation")
	}
	other := "PC2"
	if slot == other {
		other = "PC4"
	}
	if _, e = v.AuthenticateNativeHistory(raw, other); e == nil {
		t.Fatal("historical Node swap")
	}
}

func TestNativeExpiryIsDeterministicLeasePlanBound(t *testing.T) {
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
	for name, change := range map[string]func(){
		"lease-shorter": func() {
			for id, o := range v.ctx.Operations {
				o.ExpiresAt = v.ctx.Now.Add(30 * time.Second)
				v.ctx.Operations[id] = o
			}
		},
		"plan-shorter": func() {
			v.ctx.SemanticInputs.(map[string]any)["plan"].(map[string]any)["expiresAt"] = v.ctx.Now.Add(30 * time.Second).Format("2006-01-02T15:04:05Z")
		},
		"wrong-challenge-nonce": func() {
			for id, c := range v.ctx.Challenges {
				c.Nonce = strings.Repeat("e", 64)
				v.ctx.Challenges[id] = c
			}
		},
		"wrong-challenge-epoch": func() {
			for id, c := range v.ctx.Challenges {
				c.FenceEpoch++
				v.ctx.Challenges[id] = c
			}
		},
	} {
		t.Run(name, func(t *testing.T) {
			fresh, e := NewVerifier(f.installed, f.context)
			if e != nil {
				t.Fatal(e)
			}
			v = fresh
			change()
			if _, e = v.verifyProof(loc, p, d, f.packet.Referents); e == nil {
				t.Fatal("native bound/challenge accepted")
			}
		})
	}
}

func TestNativeCertificateNotAfterCapsDerivedReference(t *testing.T) {
	f := newCryptoFixtureMutated(t, nil, cryptoFixtureOptions{NativeLifetime: 20 * time.Second})
	v, e := NewVerifier(f.installed, f.context)
	if e != nil {
		t.Fatal(e)
	}
	if _, e = v.Verify(f.packet); e != nil {
		t.Fatal(e)
	}
	p := parsedPacket(t, f.packet)
	count := 0
	for _, loc := range allLocations(t, v, p) {
		if loc.reference["contractId"] == "saintvision-proof-node-floor-v2:1" {
			if loc.reference["validUntil"] != f.context.Now.Add(20*time.Second).Format("2006-01-02T15:04:05Z") {
				t.Fatal("native expiry ignored certificate cap")
			}
			count++
		}
	}
	if count == 0 {
		t.Fatal("native cap was not exercised")
	}
}

func TestMissingProofAuthenticationPrecedesDerivedEvaluation(t *testing.T) {
	f := newCryptoFixture(t)
	v, e := NewVerifier(f.installed, f.context)
	if e != nil {
		t.Fatal(e)
	}
	p := parsedPacket(t, f.packet)
	set := p["cohort-36"].(map[string]any)
	set["operationId"] = "foreign-operation"
	b, e := CanonicalJSON(set)
	if e != nil {
		t.Fatal(e)
	}
	f.packet.Records["cohort-36"] = b
	for hash := range f.packet.Referents {
		delete(f.packet.Referents, hash)
		break
	}
	if _, e = v.Verify(f.packet); e == nil || strings.Contains(e.Error(), "binding mismatch") {
		t.Fatalf("derived evaluation preceded required proof authentication: %v", e)
	}
}
