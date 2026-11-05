package migrationverify

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"sort"
	"time"
)

// Packet is untrusted, immutable serialized input only. It has no trust policy,
// verifier, key grant, clock, digest-mode or callback selection fields.
type Packet struct {
	Records   map[string][]byte
	Referents map[string][]byte
}

// Report is authentication of a supplied offline history, never operational
// admission. Historical proofs are not transferable as fresh authorization.
type Report struct {
	Classification                           string
	Records, ProofReferences, RealSignatures int
	Digests                                  map[string]string
}
type verifiedPacket struct {
	payloads  map[string]any
	digests   map[string]string
	proofs    map[string][]authenticatedProof
	report    Report
	referents map[string][]byte // Only the bounded per-call snapshot.
}

var outerDomains = map[string]string{
	"successor-plan":    "saintvision/plain-agent-migration-plan/v1",
	"migration-event":   "saintvision/plain-agent-migration-event/v1",
	"migration-journal": "saintvision/plain-agent-migration-journal/v1",
	"terminal-seal":     "saintvision/plain-agent-migration-seal/v1",
	"operation-lease":   "saintvision/agent-mutation-fence/v1",
	"runtime-inventory": "saintvision/node-runtime-inventory/v1",
}
var outerRoles = map[string]string{"successor-plan": "root-plan", "migration-event": "host-helper", "migration-journal": "host-helper", "terminal-seal": "root-seal", "operation-lease": "root-fence", "runtime-inventory": "cp-inventory"}

func (v *Verifier) Verify(packet Packet) (Report, error) {
	x, e := v.verify(packet)
	if e != nil {
		return Report{}, e
	}
	return x.report, nil
}

// The caller owns packet maps/slices exclusively during this call. Copying is
// defensive isolation, not synchronization with concurrent caller mutation.
func snapshotPacket(packet Packet) (Packet, error) {
	if len(packet.Records) > 4096 || len(packet.Referents) > 8192 {
		return Packet{}, errors.New("packet object-count bound")
	}
	total := 0
	for _, collection := range []map[string][]byte{packet.Records, packet.Referents} {
		for _, raw := range collection {
			if len(raw) > (32<<20)-total {
				return Packet{}, errors.New("packet byte bound")
			}
			total += len(raw)
		}
	}
	out := Packet{Records: make(map[string][]byte, len(packet.Records)), Referents: make(map[string][]byte, len(packet.Referents))}
	for id, raw := range packet.Records {
		out.Records[id] = append([]byte(nil), raw...)
	}
	for id, raw := range packet.Referents {
		out.Referents[id] = append([]byte(nil), raw...)
	}
	return out, nil
}
func (v *Verifier) verify(packet Packet) (*verifiedPacket, error) {
	if v == nil || v.contracts == nil || v.schemas == nil || v.graph == nil {
		return nil, errors.New("missing installed verifier")
	}
	if len(packet.Records) != len(v.trust.NodeKinds) {
		return nil, errors.New("missing or extra packet records")
	}
	var e error
	packet, e = snapshotPacket(packet)
	if e != nil {
		return nil, e
	}
	x := &verifiedPacket{payloads: map[string]any{}, proofs: map[string][]authenticatedProof{}, referents: packet.Referents}
	for id, raw := range packet.Records {
		kind, ok := v.trust.NodeKinds[id]
		if !ok {
			return nil, errors.New("unknown record identity")
		}
		p, e := ParseJSON(raw)
		if e != nil {
			return nil, e
		}
		if e = v.schemas.Validate(kind, p); e != nil {
			return nil, fmt.Errorf("%s: %w", id, e)
		}
		b, e := CanonicalJSON(p)
		if e != nil {
			return nil, e
		}
		if !bytes.Equal(raw, b) {
			return nil, errors.New("record is not exact canonical bytes")
		}
		if e = checkCalendars(p); e != nil {
			return nil, e
		}
		x.payloads[id] = p
	}
	// Only original signed/transport identities are calculated here. No derived
	// cohort digest is evaluated until every original signature, scoped proof,
	// operation lease and CP head readback below has authenticated successfully.
	d := map[string]string{}
	for id, p := range x.payloads {
		if v.trust.NodeKinds[id] == "cohort-projection-set" {
			continue
		}
		digest, e := ArtifactDigest(v.trust.NodeKinds[id], p)
		if e != nil {
			return nil, e
		}
		d[id] = digest
	}
	plan, e := pointer(x.payloads["plan"], "/body")
	if e != nil {
		return nil, e
	}
	pm, e := object(plan)
	if e != nil {
		return nil, e
	}
	if pm["canonicalContractSHA256"] != v.trust.RegistrySHA256 {
		return nil, errors.New("plan does not select installed registry")
	}
	if e = v.checkRegisteredMembers(pm); e != nil {
		return nil, e
	}
	// Authenticate all original signed records before processing unsigned
	// projections or proof-derived joins. An unsigned object never signs another.
	for _, id := range v.graph.order {
		kind := v.trust.NodeKinds[id]
		domain, signed := outerDomains[kind]
		if !signed {
			continue
		}
		m, _ := object(x.payloads[id])
		body, _ := object(m["body"])
		signer, _ := object(m["signer"])
		role := outerRoles[kind]
		if signer["role"] != role {
			return nil, errors.New("record signer role is not kind-pinned")
		}
		authority, e := v.outerAuthority(kind, body)
		if e != nil {
			return nil, e
		}
		spki, e := text(signer["keySPKISHA256"])
		if e != nil {
			return nil, e
		}
		use, e := v.recordUse(id, x.payloads, d)
		if e != nil {
			return nil, e
		}
		key, e := v.keyAt(role, authority, spki, use.at)
		if e != nil {
			return nil, e
		}
		b, e := CanonicalJSON(body)
		if e != nil {
			return nil, e
		}
		sig, e := exactHex(signer["signatureHex"].(string), 64)
		if e != nil {
			return nil, e
		}
		if e = verifyEd25519(key, append([]byte(domain+"\x00"), b...), sig); e != nil {
			return nil, fmt.Errorf("record %s: %w", id, e)
		}
		x.report.RealSignatures++
	}
	for _, op := range v.ctx.History.Operations {
		found := false
		for id, digest := range d {
			if digest != op.LeaseEnvelopeSHA256 || v.trust.NodeKinds[id] != "operation-lease" {
				continue
			}
			body, _ := pointer(x.payloads[id], "/body")
			b, _ := object(body)
			if !v.leaseScopesMatch(b) || b["planEnvelopeSHA256"] != d["plan"] || b["mode"] != "HELD" || b["operationId"] != op.OperationID || b["migrationId"] != op.MigrationID || !equal(b["fenceEpoch"], json.Number(fmt.Sprint(op.FenceEpoch))) || b["acquiredAt"] != op.AcquiredAt.Format("2006-01-02T15:04:05Z") || b["expiresAt"] != op.ExpiresAt.Format("2006-01-02T15:04:05Z") {
				return nil, errors.New("historical operation differs from authenticated original lease")
			}
			found = true
		}
		if !found {
			return nil, errors.New("historical operation has no authenticated original lease")
		}
	}
	used := map[string]bool{}
	for _, id := range v.graph.order {
		if e = visitProofs(id, v.trust.NodeKinds[id], x.payloads[id], func(loc proofLocation) error {
			p, e := v.verifyProof(loc, x.payloads, d, packet.Referents)
			if e != nil {
				return fmt.Errorf("%s%s: %w", id, loc.path, e)
			}
			hash := loc.reference["artifactSHA256"].(string)
			used[hash] = true
			x.proofs[hash] = append(x.proofs[hash], p)
			x.report.ProofReferences++
			x.report.RealSignatures++
			return nil
		}); e != nil {
			return nil, e
		}
	}
	if len(used) != len(packet.Referents) {
		return nil, errors.New("extra unconsumed/foreign proof referents")
	}
	for hash, raw := range packet.Referents {
		if !used[hash] || shaHex(raw) != hash {
			return nil, errors.New("referent identity mismatch")
		}
	}
	d, e = v.graph.check(v.ctx.SemanticInputs, x.payloads, v.trust.NodeKinds)
	if e != nil {
		return nil, e
	}
	x.digests = d
	x.report.Classification = "AUTHENTICATED_OFFLINE_HISTORY_NOT_OPERATIONAL_AUTHORIZATION"
	x.report.Records = len(x.payloads)
	x.report.Digests = d
	return x, nil
}

func (v *Verifier) checkRegisteredMembers(plan map[string]any) error {
	mi, ok := plan["memberInputs"].([]any)
	if !ok || len(mi) != len(v.trust.Members) {
		return errors.New("incomplete plan cohort")
	}
	for i, m := range v.trust.Members {
		x, e := object(mi[i])
		if e != nil {
			return e
		}
		if x["slot"] != m.Slot || !equal(x["scope"], m.Scope) {
			return errors.New("plan ordered identity differs from external cohort")
		}
	}
	facts, e := pointer(v.ctx.SemanticInputs, "/facts/cohortId")
	if e != nil || facts != v.trust.CohortID {
		return errors.New("trusted facts cohort mismatch")
	}
	return nil
}

func (v *Verifier) outerAuthority(kind string, body map[string]any) (any, error) {
	if kind == "migration-journal" || kind == "terminal-seal" {
		scope := body["scope"]
		for _, m := range v.trust.Members {
			if equal(m.Scope, scope) {
				return nodeAuthority(m.Scope), nil
			}
		}
		return nil, errors.New("unknown signed Node scope")
	}
	if kind == "migration-event" {
		if slot, ok := body["targetSlot"].(string); ok && slot != "" {
			m, e := v.member(slot)
			if e != nil {
				return nil, e
			}
			return nodeAuthority(m.Scope), nil
		}
	}
	return v.cohortAuthority(), nil
}

func checkCalendars(v any) error {
	switch x := v.(type) {
	case map[string]any:
		for k, v := range x {
			switch k {
			case "createdAt", "expiresAt", "recordedAt", "publishedAt", "sealedAt", "acquiredAt", "observedAt", "validUntil", "leafDeadline", "caDeadline", "policyDeadline", "maintenanceStart", "maintenanceEnd", "normalRenewalStart", "normalRenewalEnd", "operatorWindowStart", "operatorWindowEnd":
				if s, ok := v.(string); ok {
					if _, e := strictTime(s); e != nil {
						return fmt.Errorf("%s: %w", k, e)
					}
				}
			}
			if e := checkCalendars(v); e != nil {
				return e
			}
		}
	case []any:
		for _, v := range x {
			if e := checkCalendars(v); e != nil {
				return e
			}
		}
	}
	return nil
}

// VerifyCurrentProjectionSet recomputes an unsigned set only after authenticating
// all original records/proofs and independently matching the complete current
// external context. Its return is derived DATA, never an attestation or permit.
func (v *Verifier) VerifyCurrentProjectionSet(packet Packet, setID string) (string, error) {
	x, e := v.verify(packet)
	if e != nil {
		return "", e
	}
	c := v.ctx.Current
	if c == nil || c.SetID != setID || v.trust.NodeKinds[setID] != "cohort-projection-set" {
		return "", errors.New("no trusted current set context")
	}
	m, e := object(x.payloads[setID])
	if e != nil {
		return "", e
	}
	for k, w := range map[string]any{"planEnvelopeSHA256": c.PlanEnvelopeSHA256, "migrationId": c.MigrationID, "cohortId": v.trust.CohortID, "operationId": c.OperationID, "leaseEnvelopeSHA256": c.LeaseEnvelopeSHA256, "inventoryHead": c.InventoryHead, "inventoryHeadReadbackSHA256": c.InventoryReadbackSHA256, "fenceEpoch": json.Number(fmt.Sprint(c.FenceEpoch)), "sequence": json.Number(fmt.Sprint(c.Sequence))} {
		if !equal(m[k], w) {
			return "", fmt.Errorf("current set %s mismatch", k)
		}
	}
	if x.digests["plan"] != c.PlanEnvelopeSHA256 || len(c.MemberProjectionSHA256) != 2 {
		return "", errors.New("current plan/member binding absent")
	}
	find := func(hash, kind string) (map[string]any, error) {
		ids := []string{}
		for id, d := range x.digests {
			if d == hash && v.trust.NodeKinds[id] == kind {
				ids = append(ids, id)
			}
		}
		sort.Strings(ids)
		if len(ids) != 1 {
			return nil, errors.New("missing or ambiguous authenticated original")
		}
		return object(x.payloads[ids[0]])
	}
	lease, e := find(c.LeaseEnvelopeSHA256, "operation-lease")
	if e != nil {
		return "", e
	}
	lb, _ := object(lease["body"])
	if lb["mode"] != "HELD" {
		return "", errors.New("current lease is RELEASED or not HELD")
	}
	if e = v.latestCurrent(x, c); e != nil {
		return "", e
	}
	op, e := v.operation(c.OperationID)
	if e != nil {
		return "", e
	}
	if op.MigrationID != c.MigrationID || op.FenceEpoch != c.FenceEpoch || v.ctx.Now.Before(op.AcquiredAt) || !v.ctx.Now.Before(op.ExpiresAt) {
		return "", errors.New("current operation/epoch expired or mismatched")
	}
	if c.LeaseEnvelopeSHA256 != op.LeaseEnvelopeSHA256 || !v.leaseScopesMatch(lb) {
		return "", errors.New("current lease differs from exact trusted operation/cohort")
	}
	if lb["acquiredAt"] != op.AcquiredAt.Format(time.RFC3339) || lb["expiresAt"] != op.ExpiresAt.Format(time.RFC3339) {
		return "", errors.New("current operation window differs from authenticated HELD lease")
	}
	if lb["operationId"] != c.OperationID || lb["migrationId"] != c.MigrationID || !equal(lb["fenceEpoch"], json.Number(fmt.Sprint(c.FenceEpoch))) {
		return "", errors.New("current signed lease/fence mismatch")
	}
	expires, e := strictTime(lb["expiresAt"].(string))
	if e != nil || !v.ctx.Now.Before(expires) {
		return "", errors.New("current signed lease expired")
	}
	readback := false
	for _, p := range x.proofs[c.InventoryReadbackSHA256] {
		if p.contract == "saintvision-proof-inventory-head-readback:1" && p.operation == c.OperationID && p.migration == c.MigrationID && v.ctx.Now.Before(p.until) && !v.ctx.Now.Before(p.observed.Add(-30*time.Second)) && v.ctx.Now.Sub(p.observed) <= 120*time.Second {
			subject, _ := object(p.subject)
			head, _ := object(c.InventoryHead)
			if subject["presence"] == head["presence"] && equal(subject["envelopeSHA256"], head["envelopeSHA256"]) {
				readback = true
			}
		}
	}
	if !readback {
		return "", errors.New("current genuine CP head readback absent")
	}
	if e = v.currentReadback(c, x); e != nil {
		return "", e
	}
	head, e := object(c.InventoryHead)
	if e != nil {
		return "", e
	}
	if head["presence"] == "PRESENT" {
		hash, e := text(head["envelopeSHA256"])
		if e != nil {
			return "", e
		}
		if _, e = find(hash, "runtime-inventory"); e != nil {
			return "", e
		}
	}
	members, ok := m["members"].([]any)
	if !ok || len(members) != 2 {
		return "", errors.New("incomplete derived member set")
	}
	for i, reg := range v.trust.Members {
		mm, _ := object(members[i])
		if mm["slot"] != reg.Slot || !equal(mm["scope"], reg.Scope) || mm["projectionEnvelopeSHA256"] != c.MemberProjectionSHA256[i] {
			return "", errors.New("current exact ordered member mismatch")
		}
		p, e := find(c.MemberProjectionSHA256[i], "migration-journal")
		if e != nil {
			return "", e
		}
		b, _ := object(p["body"])
		if !equal(b["scope"], reg.Scope) || b["planEnvelopeSHA256"] != c.PlanEnvelopeSHA256 || b["ownerLeaseEnvelopeSHA256"] != c.LeaseEnvelopeSHA256 {
			return "", errors.New("current original Node projection binding mismatch")
		}
	}
	if e = v.currentNativeWitnesses(c, x); e != nil {
		return "", e
	}
	return ArtifactDigest("cohort-projection-set", m)
}
