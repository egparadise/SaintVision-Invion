package migrationverify

import (
	"crypto/ed25519"
	"crypto/rand"
	"encoding/hex"
	"math/big"
	"testing"
)

func unhex(t *testing.T, s string) []byte {
	t.Helper()
	b, e := hex.DecodeString(s)
	if e != nil {
		t.Fatal(e)
	}
	return b
}

func TestRFC8032StrictVerification(t *testing.T) {
	identityForgeryKey := append([]byte{1}, make([]byte, 31)...)
	identityForgerySignature := append(append([]byte(nil), identityForgeryKey...), make([]byte, 32)...)
	if e := verifyEd25519(identityForgeryKey, nil, identityForgerySignature); e == nil {
		t.Fatal("identity-key/signature forgery accepted")
	}
	t.Logf("public identity forgery: stdlib accepted=%v; strict product rejected=true", ed25519.Verify(identityForgeryKey, nil, identityForgerySignature))
	// RFC8032 section 7.1 TEST 1, empty message. Public data, not a test key
	// registered with any verifier or a reusable runtime credential.
	key := unhex(t, "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
	sig := unhex(t, "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b")
	if e := verifyEd25519(key, nil, sig); e != nil {
		t.Fatal(e)
	}
	if e := verifyEd25519(key, []byte("changed"), sig); e == nil {
		t.Fatal("message tamper")
	}
	for _, s := range []string{
		"0100000000000000000000000000000000000000000000000000000000000000", // identity
		"0000000000000000000000000000000000000000000000000000000000000000", // order four
		"ecffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7f", // order two
		"edffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7f", // y=p
		"eeffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7f", // y>p
		"0100000000000000000000000000000000000000000000000000000000000080", // x=0 sign1
	} {
		p := unhex(t, s)
		if e := decodePrimePoint(p); e == nil {
			t.Fatalf("accepted forbidden point %s", s)
		}
		bad := append([]byte(nil), sig...)
		copy(bad, p)
		if e := verifyEd25519(key, nil, bad); e == nil {
			t.Fatal("bad R")
		}
		if e := verifyEd25519(p, nil, sig); e == nil {
			t.Fatal("bad A")
		}
	}
	for _, scalar := range []*big.Int{groupL, new(big.Int).Add(littleInt(sig[32:]), groupL)} {
		bad := append([]byte(nil), sig...)
		copy(bad[32:], littleBytes(scalar))
		if e := verifyEd25519(key, nil, bad); e == nil {
			t.Fatal("S>=L accepted")
		}
	}
	// Add the order-two point to a valid prime-order point. The resulting
	// canonical, on-curve, mixed-order encoding must still be rejected.
	mixed := append([]byte(nil), key...)
	sign := mixed[31] & 0x80
	mixed[31] &= 0x7f
	y := littleInt(mixed)
	negY := minus(big.NewInt(0), y)
	mixed = littleBytes(negY)
	mixed[31] |= sign ^ 0x80
	if e := decodePrimePoint(mixed); e == nil {
		t.Fatal("mixed-order point accepted")
	}
}

func littleBytes(n *big.Int) []byte {
	b := n.Bytes()
	out := make([]byte, 32)
	for i := range b {
		out[i] = b[len(b)-1-i]
	}
	return out
}

func TestEphemeralEd25519AndSPKI(t *testing.T) {
	pub, key, e := ed25519.GenerateKey(rand.Reader)
	if e != nil {
		t.Fatal(e)
	}
	msg := []byte("explicit ephemeral TEST signing only")
	if e := verifyEd25519(pub, msg, ed25519.Sign(key, msg)); e != nil {
		t.Fatal(e)
	}
	h, e := publicSPKI(pub)
	if e != nil {
		t.Fatal(e)
	}
	if h == shaHex(pub) {
		t.Fatal("SPKI confused with raw key")
	}
	if _, e := exactHex("AA", 1); e == nil {
		t.Fatal("uppercase hex")
	}
}
