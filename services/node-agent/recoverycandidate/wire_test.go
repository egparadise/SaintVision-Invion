package recoverycandidate

import (
	"bytes"
	"crypto/ed25519"
	"crypto/rand"
	"testing"
)

func TestStrictWireRefusesAmbiguity(t *testing.T) {
	for _, raw := range []string{`{"a":1,"a":2}`,`{"a":1.0}`,`{"a":1e1}`,`{"a":9007199254740992}`,`{"a":"<"}`,`{"a":1} `,`{"a":1} {}`,`[]`} {
		if _, err := Parse([]byte(raw)); err == nil { t.Fatalf("accepted ambiguous wire: %s",raw) }
	}
	if _, err := Parse(bytes.Repeat([]byte{'a'},MaxBytes+1)); err == nil { t.Fatal("unbounded wire accepted") }
}

func TestDistinctSignatureDomainsAndActors(t *testing.T) {
	pub, key, _ := ed25519.GenerateKey(rand.Reader)
	other, _, _ := ed25519.GenerateKey(rand.Reader)
	envelope, err := Sign(map[string]any{"schema":"sv-expired-policy-nonserving-proof:1","serving":false},ProofDomain,key)
	if err != nil { t.Fatal(err) }
	if _, _, err = Verify(envelope,ProofDomain,pub); err != nil { t.Fatal(err) }
	for _, domain := range []string{AuthorizationDomain,OperatorDomain,AckDomain,CheckpointDomain,"saintvision/node-peer-policy-floor/v2\x00"} {
		if _, _, err = Verify(envelope,domain,pub); err == nil { t.Fatal("cross-domain signature accepted") }
	}
	if _, _, err = Verify(envelope,ProofDomain,other); err == nil { t.Fatal("wrong actor accepted") }
}

func TestJournalExactBytesNotRewritten(t *testing.T) {
	raw := []byte("{\"Tenant\":\"t\",\"Node\":\"n\",\"Epoch\":\"e\"}")
	if _, err := ParseJournal(raw); err != nil { t.Fatal(err) }
	if _, err := Parse(raw); err == nil { t.Fatal("noncanonical protocol accepted") }
	if _, err := ParseJournal([]byte(`{"Version":1,"Version":2}`)); err == nil { t.Fatal("duplicate journal field accepted") }
}
