package migrationverify

import (
	"errors"
	"fmt"
	"time"
)

type proofUse struct {
	at   time.Time
	live bool
}

func timeAt(value any, path string) (time.Time, error) {
	x, e := pointer(value, path)
	if e != nil {
		return time.Time{}, fmt.Errorf("required time %s: %w", path, e)
	}
	s, e := text(x)
	if e != nil {
		return time.Time{}, fmt.Errorf("required time %s: %w", path, e)
	}
	return strictTime(s)
}

func validateSemanticInputs(value any) error {
	for _, path := range []string{"", "/plan", "/facts", "/policy", "/containers"} {
		x, e := pointer(value, path)
		if e != nil {
			return fmt.Errorf("trusted SemanticInputs%s: %w", path, e)
		}
		if _, e = object(x); e != nil {
			return fmt.Errorf("trusted SemanticInputs%s: %w", path, e)
		}
	}
	if _, e := timeAt(value, "/plan/expiresAt"); e != nil {
		return fmt.Errorf("trusted SemanticInputs: %w", e)
	}
	plan, _ := pointer(value, "/plan")
	if _, e := (&Verifier{}).evidenceAge(plan); e != nil {
		return fmt.Errorf("trusted SemanticInputs: %w", e)
	}
	return nil
}

// recordUse derives the consuming instant from the signed containing record or
// its exact causal signed event. All original signatures are verified before
// proof use, and graph validation subsequently checks the complete causal joins.
// It is also used to select the key interval while authenticating that record;
// a forged timestamp cannot survive the record signature check.
func (v *Verifier) recordUse(id string, payloads map[string]any, digests map[string]string) (proofUse, error) {
	kind := v.trust.NodeKinds[id]
	p, e := object(payloads[id])
	if e != nil {
		return proofUse{}, e
	}
	b := p
	if x, ok := p["body"]; ok {
		b, e = object(x)
		if e != nil {
			return proofUse{}, e
		}
	}
	field := map[string]string{"successor-plan": "createdAt", "migration-event": "recordedAt", "runtime-inventory": "publishedAt", "terminal-seal": "sealedAt"}[kind]
	var at time.Time
	if kind == "operation-lease" && b["mode"] == "HELD" {
		field = "acquiredAt"
	}
	if field != "" {
		at, e = timeAt(b, "/"+field)
	} else {
		var chosen map[string]any
		var sequence int64
		for eid, value := range payloads {
			if v.trust.NodeKinds[eid] != "migration-event" {
				continue
			}
			eb, er := pointer(value, "/body")
			if er != nil {
				return proofUse{}, er
			}
			event, er := object(eb)
			if er != nil {
				return proofUse{}, er
			}
			seq, er := number64(event["sequence"])
			if er != nil {
				return proofUse{}, er
			}
			match := false
			switch kind {
			case "api-request":
				match = event["requestSHA256"] == digests[id] && event["operationId"] == b["operationId"] && event["planEnvelopeSHA256"] == b["planEnvelopeSHA256"] && event["method"] == b["method"]
			case "migration-journal":
				latest, er := object(b["latestEvent"])
				if er != nil {
					return proofUse{}, er
				}
				match = latest["envelopeSHA256"] == digests[eid] && equal(latest["sequence"], event["sequence"]) && b["migrationId"] == event["migrationId"] && b["planEnvelopeSHA256"] == event["planEnvelopeSHA256"]
			case "operation-lease":
				match = b["mode"] == "RELEASED" && event["method"] == "release" && event["recordKind"] == "outcome" && event["operationId"] == b["operationId"] && event["migrationId"] == b["migrationId"] && event["planEnvelopeSHA256"] == b["planEnvelopeSHA256"] && event["leaseEnvelopeSHA256"] == b["priorFenceEnvelopeSHA256"] && equal(event["fenceEpoch"], b["fenceEpoch"])
			}
			if match && (chosen == nil || (kind == "api-request" && seq < sequence) || (kind == "operation-lease" && seq > sequence)) {
				chosen, sequence = event, seq
			}
		}
		if chosen == nil {
			return proofUse{}, fmt.Errorf("%s lacks exact signed consuming event", id)
		}
		at, e = timeAt(chosen, "/recordedAt")
	}
	if e != nil {
		return proofUse{}, e
	}
	if at.After(v.ctx.Now) {
		return proofUse{}, errors.New("consuming record is after trusted Now")
	}
	return proofUse{at: at}, nil
}

func number64(value any) (int64, error) {
	s, e := textNumber(value)
	if e != nil {
		return 0, e
	}
	var n int64
	_, e = fmt.Sscan(s, &n)
	return n, e
}
