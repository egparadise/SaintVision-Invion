package transport

import (
	"bytes"
	"crypto/ed25519"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func TestPeerFloorCanonicalCrossLanguageVectors(t *testing.T) {
	raw, err := os.ReadFile(filepath.Join("..", "..", "..", "tests", "fixtures", "fleet5-floor-v2-canonical-vectors.json"))
	if err != nil {
		t.Fatal(err)
	}
	var fixture struct {
		Cases []struct {
			Name                     string
			Body                     json.RawMessage
			ExpectedCanonicalUTF8Hex string
		}
	}
	if err := json.Unmarshal(raw, &fixture); err != nil {
		t.Fatal(err)
	}
	seed := make([]byte, ed25519.SeedSize)
	for i := range seed {
		seed[i] = byte(i)
	} // public deterministic UNIT TEST key only
	key := ed25519.NewKeyFromSeed(seed)
	results := []map[string]any{}
	for _, vector := range fixture.Cases {
		t.Run(vector.Name, func(t *testing.T) {
			var body map[string]any
			decoder := json.NewDecoder(bytes.NewReader(vector.Body))
			decoder.UseNumber()
			if err := decoder.Decode(&body); err != nil {
				t.Fatal(err)
			}
			encoded, err := CanonicalPeerFloorBody(body)
			if err != nil || hex.EncodeToString(encoded) != vector.ExpectedCanonicalUTF8Hex {
				t.Fatalf("Go body bytes differ from published vector: %v", err)
			}
			signature := ed25519.Sign(key, append([]byte(PeerFloorDomain), encoded...))
			results = append(results, map[string]any{"name": vector.Name, "canonicalUTF8Hex": hex.EncodeToString(encoded), "signatureHex": hex.EncodeToString(signature), "publicKeyHex": hex.EncodeToString(key.Public().(ed25519.PublicKey))})
		})
	}
	for _, invalid := range []any{string([]byte{0xff}), string([]byte{0xed, 0xa0, 0x80}), 1.0, json.Number("1.0"), json.Number("9007199254740992")} {
		if _, err := CanonicalPeerFloorBody(map[string]any{"invalid": invalid}); err == nil {
			t.Fatal("invalid UTF8/surrogate/number accepted")
		}
	}
	if len(results) != len(fixture.Cases) || len(results) < 6 {
		t.Fatal("missing canonical vectors")
	}
	if folder := os.Getenv("FLEET5_FIXED_NATIVE_FIXTURE"); folder != "" {
		encoded, _ := json.Marshal(results)
		if err := os.WriteFile(filepath.Join(folder, "canonical-go-results.json"), encoded, 0600); err != nil {
			t.Fatal(err)
		}
	}
}
