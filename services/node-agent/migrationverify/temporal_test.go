package migrationverify

import (
	"encoding/json"
	"strings"
	"testing"
)

func currentFromSet(t *testing.T, p map[string]any, id string) *CurrentProjectionContext {
	t.Helper()
	m, e := object(p[id])
	if e != nil {
		t.Fatal(e)
	}
	epoch, _ := m["fenceEpoch"].(json.Number).Int64()
	seq, _ := m["sequence"].(json.Number).Int64()
	members := m["members"].([]any)
	return &CurrentProjectionContext{SetID: id, MigrationID: m["migrationId"].(string), OperationID: m["operationId"].(string), PlanEnvelopeSHA256: m["planEnvelopeSHA256"].(string), LeaseEnvelopeSHA256: m["leaseEnvelopeSHA256"].(string), FenceEpoch: epoch, Sequence: seq, InventoryHead: copyJSON(m["inventoryHead"]), InventoryReadbackSHA256: m["inventoryHeadReadbackSHA256"].(string), MemberProjectionSHA256: []string{members[0].(map[string]any)["projectionEnvelopeSHA256"].(string), members[1].(map[string]any)["projectionEnvelopeSHA256"].(string)}}
}

func TestCurrentRejectsConsistentSupersededViews(t *testing.T) {
	f := newCryptoFixture(t)
	p := parsedPacket(t, f.packet)
	for _, id := range []string{"cohort-33", "cohort-34", "cohort-35"} {
		t.Run(id, func(t *testing.T) {
			ctx := f.context
			ctx.Current = currentFromSet(t, p, id)
			v, e := NewVerifier(f.installed, ctx)
			if e != nil {
				t.Fatal(e)
			}
			_, e = v.VerifyCurrentProjectionSet(f.packet, id)
			if e == nil {
				t.Fatal("accepted internally consistent obsolete current view")
			}
			if !strings.Contains(e.Error(), "superseded") && !strings.Contains(e.Error(), "RELEASED") && !strings.Contains(e.Error(), "latest") {
				t.Fatalf("wrong rejection gate: %v", e)
			}
		})
	}
}
