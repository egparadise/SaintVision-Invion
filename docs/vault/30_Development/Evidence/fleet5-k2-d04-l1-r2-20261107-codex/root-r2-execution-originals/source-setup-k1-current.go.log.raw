package migrationverify

import (
	"errors"
	"time"
)

func (v *Verifier) leaseScopesMatch(body map[string]any) bool {
	scopes, ok := body["scopes"].([]any)
	if !ok || len(scopes) != len(v.trust.Members) {
		return false
	}
	for i, m := range v.trust.Members {
		s, e := object(scopes[i])
		if e != nil || !equal(s["scope"], m.Scope) {
			return false
		}
	}
	return true
}

func (v *Verifier) latestCurrent(x *verifiedPacket, c *CurrentProjectionContext) error {
	var latest int64
	for id, p := range x.payloads {
		kind := v.trust.NodeKinds[id]
		if kind != "operation-lease" && kind != "migration-event" {
			continue
		}
		body, e := pointer(p, "/body")
		if e != nil {
			return e
		}
		b, e := object(body)
		if e != nil {
			return e
		}
		if b["migrationId"] != c.MigrationID || b["planEnvelopeSHA256"] != c.PlanEnvelopeSHA256 {
			continue
		}
		epoch, e := number64(b["fenceEpoch"])
		if e != nil {
			return e
		}
		if kind == "operation-lease" {
			if !v.leaseScopesMatch(b) {
				continue
			}
			if b["operationId"] == c.OperationID && epoch == c.FenceEpoch && b["mode"] == "RELEASED" {
				return errors.New("current operation is RELEASED in authenticated history")
			}
			if epoch > c.FenceEpoch {
				return errors.New("current fence superseded by authenticated higher cohort epoch")
			}
		} else if b["operationId"] == c.OperationID && epoch == c.FenceEpoch {
			seq, e := number64(b["sequence"])
			if e != nil {
				return e
			}
			if seq > latest {
				latest = seq
			}
		}
	}
	if latest == 0 || c.Sequence != latest {
		return errors.New("current set is not latest authenticated operation sequence")
	}
	return nil
}

func (v *Verifier) currentNativeWitnesses(c *CurrentProjectionContext, x *verifiedPacket) error {
	if len(c.NativeWitnesses) != len(v.trust.Members) {
		return errors.New("current signed native witnesses absent or incomplete")
	}
	op, e := v.operation(c.OperationID)
	if e != nil {
		return e
	}
	contract := v.contracts.byID["saintvision-proof-node-floor-v2:1"]
	head, e := object(c.InventoryHead)
	if e != nil {
		return e
	}
	if head["presence"] != "PRESENT" {
		return errors.New("current native state lacks authenticated inventory head declaration")
	}
	for i, member := range v.trust.Members {
		w := c.NativeWitnesses[i]
		if w.Slot != member.Slot {
			return errors.New("current native witness order/member mismatch")
		}
		var expected any
		// The retained declaration supplies expected state, not freshness. Scope,
		// executable, journal identity and policy/floor remain independently bound
		// through subject recipes; only the independently issued nonce is new.
		for id, p := range x.payloads {
			if v.trust.NodeKinds[id] != "runtime-inventory" || x.digests[id] != head["envelopeSHA256"] {
				continue
			}
			e = visitProofs(id, "runtime-inventory", p, func(loc proofLocation) error {
				if loc.reference["contractId"] != contract.id {
					return nil
				}
				sub, _, err := v.subject(loc, x.payloads, x.digests, contract)
				if err != nil {
					return err
				}
				m, err := object(sub)
				if err != nil {
					return err
				}
				if equal(m["scope"], member.Scope) {
					if expected != nil && !equal(expected, sub) {
						return errors.New("conflicting current native declarations")
					}
					expected = copyJSON(sub)
				}
				return nil
			})
			if e != nil {
				return e
			}
		}
		if expected == nil {
			return errors.New("current native expected state absent")
		}
		scopeHash, e := canonicalHash(member.Scope)
		if e != nil {
			return e
		}
		challenge, ok := v.ctx.Challenges[op.OperationID+"\x00"+scopeHash]
		if !ok {
			return errors.New("current native challenge absent")
		}
		expected.(map[string]any)["nonce"] = challenge.Nonce
		original, e := v.authenticateNativeOriginal(w.Raw, w.Slot, v.ctx.Now)
		if e != nil {
			return e
		}
		plan, e := pointer(v.ctx.SemanticInputs, "/plan")
		if e != nil {
			return e
		}
		age, e := v.evidenceAge(plan)
		if e != nil {
			return e
		}
		expiry, e := timeAt(plan, "/expiresAt")
		if e != nil {
			return e
		}
		until := original.observed.Add(age)
		for _, bound := range []time.Time{original.certificate.NotAfter.Truncate(time.Second), expiry, op.ExpiresAt} {
			if bound.Before(until) {
				until = bound
			}
		}
		ref := map[string]any{"signerKeySPKISHA256": original.spki, "observedAt": original.observed.Format(time.RFC3339), "validUntil": until.Format(time.RFC3339)}
		if _, e = v.verifyNativeAt(w.Raw, expected, ref, contract, op, proofUse{at: v.ctx.Now, live: true}); e != nil {
			return e
		}
	}
	return nil
}

func (v *Verifier) currentReadback(c *CurrentProjectionContext, x *verifiedPacket) error {
	found := false
	for id, p := range x.payloads {
		e := visitProofs(id, v.trust.NodeKinds[id], p, func(loc proofLocation) error {
			if loc.reference["artifactSHA256"] != c.InventoryReadbackSHA256 {
				return nil
			}
			a, err := v.verifyProofAt(loc, x.payloads, x.digests, x.referents, proofUse{at: v.ctx.Now, live: true})
			if err == nil && a.contract == "saintvision-proof-inventory-head-readback:1" && a.operation == c.OperationID && a.migration == c.MigrationID {
				found = true
			}
			return nil
		})
		if e != nil {
			return e
		}
	}
	if !found {
		return errors.New("current head readback lacks fresh current role/operation/lease binding")
	}
	return nil
}
