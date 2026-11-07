package migrationcontext

import (
	"bytes"
	"crypto/ed25519"
	"crypto/x509"
)

// A true result is mathematical/canonical DATA under the supplied expected-key
// hypothesis, never installed trust, key quality, authorization or public success.
// The caller exclusively owns inputs during admission/copy; no concurrent or
// hostile same-process mutation isolation is claimed. No production port calls it.
func h12CheckRegistrySignature(rawRecord, publicSPKIDER []byte, independentlyExpectedSPKISHA256 string) (p02SignatureTuple, bool) {
	// p02EnvelopeLimit is the existing 2 MiB record limit (PayloadLimit is 16 MiB).
	if len(rawRecord) == 0 || len(rawRecord) > p02EnvelopeLimit || len(publicSPKIDER) == 0 || len(publicSPKIDER) > 4096 || len(independentlyExpectedSPKISHA256) != 64 {
		return p02SignatureTuple{}, false
	}
	for _, c := range independentlyExpectedSPKISHA256 {
		if !(c >= '0' && c <= '9' || c >= 'a' && c <= 'f') {
			return p02SignatureTuple{}, false
		}
	}
	raw := copyBytes(rawRecord)
	der := copyBytes(publicSPKIDER)
	v, ok := p02Decode(raw, p02EnvelopeLimit, false)
	if !ok || !p02EnvelopeSchema(v) {
		return p02SignatureTuple{}, false
	}
	e := p02ReadEnvelope(v)
	if e.body.format != p02Format || e.body.purpose != p02Purpose || e.signer.keySPKISHA256 != independentlyExpectedSPKISHA256 || hashBytes(der) != independentlyExpectedSPKISHA256 {
		return p02SignatureTuple{}, false
	}
	sig, ok := p02Unhex(e.signatureHex)
	if !ok || len(sig) != 64 {
		return p02SignatureTuple{}, false
	}
	parsed, err := x509.ParsePKIXPublicKey(der)
	if err != nil {
		return p02SignatureTuple{}, false
	}
	key, ok := parsed.(ed25519.PublicKey)
	if !ok || len(key) != 32 {
		return p02SignatureTuple{}, false
	}
	canonicalDER, err := x509.MarshalPKIXPublicKey(key)
	if err != nil || !bytes.Equal(canonicalDER, der) {
		return p02SignatureTuple{}, false
	}
	c := p02Context{envelopeValue: v}
	message := c.signingInput()
	if len(message) <= len(p02Domain) || len(message) > p02EnvelopeLimit+len(p02Domain)+1 || !ed25519.Verify(key, message, sig) {
		return p02SignatureTuple{}, false
	}
	b := e.body
	return p02SignatureTuple{format: b.format, purpose: b.purpose, domain: p02Domain, keySPKI: independentlyExpectedSPKISHA256, capsuleSHA256: b.capsuleSHA256, generation: b.provisioningGeneration, selector: b.selector, scopeSHA256: b.scopeSHA256, requestBindingSHA256: b.requestBindingSHA256, anchorVersion: b.anchorVersion, recordVersion: b.recordVersion, signingInput: message, signature: sig}, true
}
