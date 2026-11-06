package migrationverify

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"time"
)

type authenticatedProof struct {
	contract             string
	subject              any
	migration, operation string
	observed, until      time.Time
}

func normalizedMessage(domain string, body, signer map[string]any) ([]byte, error) {
	protected := map[string]any{"body": body, "signer": map[string]any{"role": signer["role"], "keySPKISHA256": signer["keySPKISHA256"]}}
	b, e := CanonicalJSON(protected)
	if e != nil {
		return nil, e
	}
	return append([]byte(domain+"\x00"), b...), nil
}

func (v *Verifier) verifyProof(loc proofLocation, payloads map[string]any, digests map[string]string, referents map[string][]byte) (authenticatedProof, error) {
	use, e := v.recordUse(loc.node, payloads, digests)
	if e != nil {
		return authenticatedProof{}, e
	}
	return v.verifyProofAt(loc, payloads, digests, referents, use)
}
func (v *Verifier) verifyProofAt(loc proofLocation, payloads map[string]any, digests map[string]string, referents map[string][]byte, use proofUse) (authenticatedProof, error) {
	var out authenticatedProof
	s, e := v.slot(loc, payloads[loc.node])
	if e != nil {
		return out, e
	}
	c := v.contracts.byID[s.ContractID]
	r := loc.reference
	for key, want := range map[string]string{"contractId": c.id, "contractSHA256": c.hash, "signatureDomainASCII": c.domain, "producerRole": c.producer, "signerRole": c.role} {
		if r[key] != want {
			return out, fmt.Errorf("proof fixed %s mismatch", key)
		}
	}
	subject, sources, e := v.subject(loc, payloads, digests, c)
	if e != nil {
		return out, e
	}
	// These two contracts additionally name the exact key in their containing
	// authenticated declaration. A different role-authorized key is insufficient.
	var declaredKey any
	switch c.kind {
	case "node-floor-v2":
		declaredKey, e = pointer(sources["input"], "/authority/nodeKeyPublicSPKISHA256")
	case "independent-code-review":
		declaredKey, e = pointer(sources["product"], "/independentReview/reviewerKeySPKISHA256")
	}
	if e != nil {
		return out, e
	}
	if declaredKey != nil && r["signerKeySPKISHA256"] != declaredKey {
		return out, errors.New("proof signer differs from exact containing Node/reviewer key")
	}
	if !equal(subject, r["typedSubject"]) {
		return out, errors.New("proof subject differs from containing authenticated sources")
	}
	sc, e := canonicalHash(subject)
	if e != nil {
		return out, e
	}
	if r["scopeSHA256"] != sc {
		return out, errors.New("proof subject digest mismatch")
	}
	hash, e := text(r["artifactSHA256"])
	if e != nil {
		return out, e
	}
	raw, ok := referents[hash]
	if !ok || shaHex(raw) != hash {
		return out, errors.New("missing exact proof referent bytes")
	}
	p, e := ParseJSON(raw)
	if e != nil {
		return out, e
	}
	if e = protocolStrings(p); e != nil {
		return out, e
	}
	if e = c.schema.Validate(p); e != nil {
		return out, fmt.Errorf("fixed %s codec schema: %w", c.codec, e)
	}
	var op OperationBinding
	if c.mode == "fresh" {
		op, e = v.proofOperationAt(sources, use.live)
		if e != nil {
			return out, e
		}
	}
	if c.codec == "native-m2-v2" {
		return v.verifyNativeAt(raw, subject, r, c, op, use)
	}
	canonical, e := CanonicalJSON(p)
	if e != nil {
		return out, e
	}
	if !bytes.Equal(raw, canonical) {
		return out, errors.New("normalized proof referent is not exact C2 bytes")
	}
	m, _ := object(p)
	body, _ := object(m["body"])
	signer, _ := object(m["signer"])
	if !equal(body["typedSubject"], subject) || body["contractId"] != c.id {
		return out, errors.New("signed proof subject/contract mismatch")
	}
	keyHash, e := text(signer["keySPKISHA256"])
	if e != nil {
		return out, e
	}
	if r["signerKeySPKISHA256"] != keyHash || signer["role"] != c.role {
		return out, errors.New("protected signer metadata mismatch")
	}
	authority, e := v.proofAuthority(loc, subject)
	if e != nil {
		return out, e
	}
	key, e := v.keyAt(c.role, authority, keyHash, use.at)
	if e != nil {
		return out, e
	}
	sigString, e := text(signer["signatureHex"])
	if e != nil {
		return out, e
	}
	sig, e := exactHex(sigString, 64)
	if e != nil {
		return out, e
	}
	msg, e := normalizedMessage(c.domain, body, signer)
	if e != nil {
		return out, e
	}
	if e = verifyEd25519(key, msg, sig); e != nil {
		return out, e
	}
	observed, e := strictTime(body["observedAt"].(string))
	if e != nil {
		return out, e
	}
	until, e := strictTime(body["validUntil"].(string))
	if e != nil {
		return out, e
	}
	if _, e = v.keyAt(c.role, authority, keyHash, observed); e != nil {
		return out, e
	}
	if body["observedAt"] != r["observedAt"] || body["validUntil"] != r["validUntil"] {
		return out, errors.New("proof metadata differs from authenticated referent")
	}
	if c.mode == "fresh" && (body["migrationId"] != op.MigrationID || body["operationId"] != op.OperationID) {
		return out, errors.New("proof signed for different current operation")
	}
	if e = v.freshnessAt(c, hash, sc, observed, until, op, sources, use); e != nil {
		return out, e
	}
	return authenticatedProof{c.id, subject, op.MigrationID, op.OperationID, observed, until}, nil
}

func (v *Verifier) proofOperation(sources map[string]any) (OperationBinding, error) {
	return v.proofOperationAt(sources, false)
}
func (v *Verifier) proofOperationAt(sources map[string]any, live bool) (OperationBinding, error) {
	a, e := object(sources["aliases"])
	if e != nil {
		return OperationBinding{}, e
	}
	id, e := text(a["operationId"])
	if e != nil {
		return OperationBinding{}, e
	}
	if live {
		return v.operation(id)
	}
	return v.historicalOperation(id)
}

func (v *Verifier) evidenceAge(plan any) (time.Duration, error) {
	x, e := pointer(plan, "/timing/maxEvidenceAgeSeconds")
	if e != nil {
		return 0, e
	}
	n, ok := x.(json.Number)
	if !ok {
		return 0, errors.New("invalid plan evidence age")
	}
	i, e := n.Int64()
	if e != nil || i <= 0 {
		return 0, errors.New("nonpositive evidence age")
	}
	if i > 120 {
		i = 120
	}
	return time.Duration(i) * time.Second, nil
}

func (v *Verifier) freshnessAt(c *proofContract, hash, subjectHash string, observed, until time.Time, op OperationBinding, sources map[string]any, use proofUse) error {
	if observed.After(until) {
		return errors.New("proof validity reversed")
	}
	plan, e := object(sources["plan"])
	if e != nil {
		return e
	}
	expiry, e := timeAt(plan, "/expiresAt")
	if e != nil {
		return e
	}
	now := v.ctx.Now
	consume := use.at
	if consume.IsZero() || consume.After(now) {
		return errors.New("invalid authenticated consuming time")
	}
	if c.mode == "fresh" {
		age, e := v.evidenceAge(plan)
		if e != nil {
			return e
		}
		if consume.Before(observed.Add(-30*time.Second)) || consume.After(observed.Add(age)) || !consume.Before(until) || !consume.Before(expiry) || consume.Before(op.AcquiredAt) || !consume.Before(op.ExpiresAt) || observed.Before(op.AcquiredAt.Add(-30*time.Second)) || !observed.Before(op.ExpiresAt) {
			return errors.New("stale/future/expired proof or trusted operation")
		}
		if op.MigrationID != plan["migrationId"] {
			return errors.New("operation migration mismatch")
		}
		return nil
	}
	p, ok := v.ctx.Publications[hash]
	if !ok || p.Status != "ACCEPTED_UNREVOKED" || p.SubjectSHA256 != subjectHash || p.PublishedAt.IsZero() || p.PublishedAt.After(now) || p.CheckedAt.After(now) || now.Sub(p.CheckedAt) > 120*time.Second || !now.Before(p.ExpiresAt) {
		return errors.New("missing current authenticated publication/nonrevocation state")
	}
	if c.mode == "immutable-provenance" {
		if p.PublishedAt.Before(observed) || p.PublishedAt.After(until) || p.PublishedAt.After(consume) {
			return errors.New("publication outside original signed validity")
		}
		return nil
	}
	if c.mode == "validity-bounded-approval" {
		if consume.Before(observed) || !consume.Before(until) || !consume.Before(expiry) || p.PublishedAt.After(consume) {
			return errors.New("approval/plan expired or future")
		}
		return nil
	}
	return errors.New("unknown fixed freshness mode")
}

func (v *Verifier) verifyNativeAt(raw []byte, subject any, ref map[string]any, c *proofContract, op OperationBinding, use proofUse) (authenticatedProof, error) {
	var out authenticatedProof
	sub, _ := object(subject)
	scope, e := object(sub["scope"])
	if e != nil {
		return out, e
	}
	var slot string
	for _, member := range v.trust.Members {
		if equal(member.Scope, scope) {
			slot = member.Slot
		}
	}
	original, e := v.authenticateNativeOriginal(raw, slot, use.at)
	if e != nil {
		return out, e
	}
	if !equal(original.subject, subject) || ref["signerKeySPKISHA256"] != original.spki {
		return out, errors.New("native original fields/certificate differ from expected reference subject")
	}
	m, cert, observed := original.body, original.certificate, original.observed
	now := use.at
	scopeHash, e := canonicalHash(scope)
	if e != nil {
		return out, e
	}
	challenges := v.ctx.History.Challenges
	if use.live {
		challenges = v.ctx.Challenges
	}
	challenge, ok := challenges[op.OperationID+"\x00"+scopeHash]
	if !ok || challenge.Nonce != m["nonce"] || challenge.MigrationID != op.MigrationID || challenge.OperationID != op.OperationID || challenge.ScopeSHA256 != scopeHash || challenge.FenceEpoch != op.FenceEpoch || now.Before(challenge.IssuedAt.Add(-30*time.Second)) || (use.live && now.Before(challenge.IssuedAt)) || !now.Before(challenge.ExpiresAt) || observed.Before(challenge.IssuedAt.Add(-30*time.Second)) || !observed.Before(challenge.ExpiresAt) {
		return out, errors.New("native nonce/observation lacks matching operation challenge")
	}
	plan, e := pointer(v.ctx.SemanticInputs, "/plan")
	if e != nil {
		return out, e
	}
	age, e := v.evidenceAge(plan)
	if e != nil {
		return out, e
	}
	expiry, e := timeAt(plan, "/expiresAt")
	if e != nil {
		return out, e
	}
	until := observed.Add(age)
	for _, bound := range []time.Time{cert.NotAfter.Truncate(time.Second), expiry, op.ExpiresAt} {
		if bound.Before(until) {
			until = bound
		}
	}
	if !until.After(observed) || ref["observedAt"] != observed.Format("2006-01-02T15:04:05Z") || ref["validUntil"] != until.Format("2006-01-02T15:04:05Z") {
		return out, errors.New("native reference time differs from VERIFIED DERIVED BOUND")
	}
	sources := map[string]any{"plan": plan}
	if e = v.freshnessAt(c, shaHex(raw), scopeHash, observed, until, op, sources, use); e != nil {
		return out, e
	}
	return authenticatedProof{c.id, subject, op.MigrationID, op.OperationID, observed, until}, nil
}
