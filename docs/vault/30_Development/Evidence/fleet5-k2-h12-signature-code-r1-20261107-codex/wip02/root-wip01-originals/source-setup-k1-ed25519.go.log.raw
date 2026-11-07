package migrationverify

import (
	"crypto/ed25519"
	"crypto/x509"
	"encoding/hex"
	"errors"
	"math/big"
)

// Point checks are additional public-input validation, not secret arithmetic.
// Extended Edwards coordinates use the complete a=-1 addition formulas. All
// signing remains outside this package. RFC8032 equation verification is then
// delegated to crypto/ed25519 with canonical prime-order A/R and S<L enforced.
var fieldP = new(big.Int).Sub(new(big.Int).Lsh(big.NewInt(1), 255), big.NewInt(19))
var groupL, _ = new(big.Int).SetString("1000000000000000000000000000000014def9dea2f79cd65812631a5cf5d3ed", 16)
var curveD = mod(new(big.Int).Mul(big.NewInt(-121665), new(big.Int).ModInverse(big.NewInt(121666), fieldP)))
var sqrtMinusOne = new(big.Int).Exp(big.NewInt(2), new(big.Int).Rsh(new(big.Int).Sub(fieldP, big.NewInt(1)), 2), fieldP)

func mod(x *big.Int) *big.Int      { return new(big.Int).Mod(x, fieldP) }
func mul(a, b *big.Int) *big.Int   { return mod(new(big.Int).Mul(a, b)) }
func plus(a, b *big.Int) *big.Int  { return mod(new(big.Int).Add(a, b)) }
func minus(a, b *big.Int) *big.Int { return mod(new(big.Int).Sub(a, b)) }
func littleInt(b []byte) *big.Int {
	r := make([]byte, len(b))
	for i := range b {
		r[len(b)-1-i] = b[i]
	}
	return new(big.Int).SetBytes(r)
}

type point struct{ x, y, z, t *big.Int }

func identity() point { return point{big.NewInt(0), big.NewInt(1), big.NewInt(1), big.NewInt(0)} }
func (p point) isIdentity() bool {
	return p.z.Sign() != 0 && p.x.Sign() == 0 && minus(p.y, p.z).Sign() == 0
}
func (p point) add(q point) point {
	a := mul(minus(p.y, p.x), minus(q.y, q.x))
	b := mul(plus(p.y, p.x), plus(q.y, q.x))
	c := mul(mul(p.t, q.t), plus(curveD, curveD))
	d := mul(plus(p.z, p.z), q.z)
	e := minus(b, a)
	f := minus(d, c)
	g := plus(d, c)
	h := plus(b, a)
	return point{mul(e, f), mul(g, h), mul(f, g), mul(e, h)}
}
func (p point) times(n *big.Int) point {
	r := identity()
	for i := n.BitLen() - 1; i >= 0; i-- {
		r = r.add(r)
		if n.Bit(i) == 1 {
			r = r.add(p)
		}
	}
	return r
}
func decodePrimePoint(raw []byte) error {
	if len(raw) != 32 {
		return errors.New("Ed25519 point length")
	}
	b := append([]byte(nil), raw...)
	sign := b[31] >> 7
	b[31] &= 0x7f
	y := littleInt(b)
	if y.Cmp(fieldP) >= 0 {
		return errors.New("noncanonical Ed25519 y")
	}
	y2 := mul(y, y)
	den := plus(mul(curveD, y2), big.NewInt(1))
	inv := new(big.Int).ModInverse(den, fieldP)
	if inv == nil {
		return errors.New("invalid Edwards denominator")
	}
	x2 := mul(minus(y2, big.NewInt(1)), inv)
	x := new(big.Int).Exp(x2, new(big.Int).Rsh(new(big.Int).Add(fieldP, big.NewInt(3)), 3), fieldP)
	if mul(x, x).Cmp(x2) != 0 {
		x = mul(x, sqrtMinusOne)
	}
	if mul(x, x).Cmp(x2) != 0 {
		return errors.New("Ed25519 point off curve")
	}
	if x.Sign() == 0 && sign != 0 {
		return errors.New("noncanonical Ed25519 sign")
	}
	if uint(x.Bit(0)) != uint(sign) {
		x = minus(big.NewInt(0), x)
	}
	p := point{x, y, big.NewInt(1), mul(x, y)}
	if p.isIdentity() || !p.times(groupL).isIdentity() {
		return errors.New("Ed25519 point is not prime-order nonidentity")
	}
	return nil
}

func verifyEd25519(key ed25519.PublicKey, message, signature []byte) error {
	if len(key) != 32 || len(signature) != 64 {
		return errors.New("Ed25519 key/signature length")
	}
	if littleInt(signature[32:]).Cmp(groupL) >= 0 {
		return errors.New("noncanonical Ed25519 scalar")
	}
	if e := decodePrimePoint(key); e != nil {
		return e
	}
	if e := decodePrimePoint(signature[:32]); e != nil {
		return e
	}
	if !ed25519.Verify(key, message, signature) {
		return errors.New("Ed25519 verification failed")
	}
	return nil
}

func publicSPKI(key ed25519.PublicKey) (string, error) {
	if len(key) != 32 {
		return "", errors.New("Ed25519 public key length")
	}
	b, e := x509.MarshalPKIXPublicKey(key)
	if e != nil {
		return "", e
	}
	return shaHex(b), nil
}
func exactHex(s string, n int) ([]byte, error) {
	if len(s) != 2*n {
		return nil, errors.New("hex length")
	}
	b, e := hex.DecodeString(s)
	if e != nil || hex.EncodeToString(b) != s {
		return nil, errors.New("noncanonical lowercase hex")
	}
	return b, nil
}
