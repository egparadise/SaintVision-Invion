package migrationverify

import (
	"crypto/ed25519"
	"encoding/hex"
	"encoding/json"
	"sync"
	"testing"
)

func TestPublicEphemeralProofVectors(t *testing.T) {
	f := newCryptoFixtureMutated(t, nil, cryptoFixtureOptions{IncludeOptionalProofs: true})
	v, e := NewVerifier(f.installed, f.context)
	if e != nil {
		t.Fatal(e)
	}
	if _, e = v.Verify(f.packet); e != nil {
		t.Fatal(e)
	}
	p := parsedPacket(t, f.packet)
	seen := map[string]bool{}
	for _, loc := range allLocations(t, v, p) {
		id := loc.reference["contractId"].(string)
		if seen[id] {
			continue
		}
		seen[id] = true
		c := v.contracts.byID[id]
		hash := loc.reference["artifactSHA256"].(string)
		raw := f.packet.Referents[hash]
		value, e := ParseJSON(raw)
		if e != nil {
			t.Fatal(e)
		}
		m := value.(map[string]any)
		var message []byte
		var signature string
		if c.codec == "native-m2-v2" {
			signature = m["nodeSignature"].(string)
			delete(m, "nodeSignature")
			b, e := CanonicalJSON(m)
			if e != nil {
				t.Fatal(e)
			}
			message = append([]byte(c.domain+"\x00"), b...)
		} else {
			body := m["body"].(map[string]any)
			signer := m["signer"].(map[string]any)
			signature = signer["signatureHex"].(string)
			message, e = normalizedMessage(c.domain, body, signer)
			if e != nil {
				t.Fatal(e)
			}
		}
		key := f.keys[loc.reference["signerKeySPKISHA256"].(string)].Public().(ed25519.PublicKey)
		vector := map[string]any{"classification": "EPHEMERAL_TEST_KEYS_REAL_SIGNATURES_NOT_LIVE_PROVENANCE", "contractId": id, "contractRawSHA256": c.hash, "schemaRawSHA256": c.schemaHash, "codec": c.codec, "freshness": c.mode, "domainASCII": c.domain, "messageHex": hex.EncodeToString(message), "publicKeyHex": hex.EncodeToString(key), "publicSPKISHA256": loc.reference["signerKeySPKISHA256"], "signatureHex": signature, "exactReferentHex": hex.EncodeToString(raw), "exactReferentSHA256": hash, "typedSubject": loc.reference["typedSubject"], "observedAt": loc.reference["observedAt"], "validUntil": loc.reference["validUntil"]}
		b, e := json.Marshal(vector)
		if e != nil {
			t.Fatal(e)
		}
		t.Logf("PUBLIC_EPHEMERAL_VECTOR %s", b)
	}
	if len(seen) != 28 {
		t.Fatal("incomplete per-contract vectors", len(seen))
	}
}

func TestVerifierConcurrentReadOnlyUse(t *testing.T) {
	f := newCryptoFixture(t)
	v, e := NewVerifier(f.installed, f.context)
	if e != nil {
		t.Fatal(e)
	}
	var wg sync.WaitGroup
	failures := make(chan error, 4)
	for i := 0; i < 4; i++ {
		wg.Add(1)
		go func() { defer wg.Done(); _, e := v.Verify(f.packet); failures <- e }()
	}
	wg.Wait()
	close(failures)
	for e := range failures {
		if e != nil {
			t.Fatal(e)
		}
	}
}
