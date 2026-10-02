//go:build linux

package runtime

import (
	"context"
	"encoding/json"
	contracts "github.com/egparadise/SaintVision-Invion/packages/contracts-go"
	"os"
	"path/filepath"
	"sync"
	"testing"
)

func quarantineRequest(c Config) contracts.BuildQuarantineRequest {
	session := "33333333-3333-4333-8333-333333333333"
	return contracts.BuildQuarantineRequest{
		SchemaVersion:  "build-quarantine-request:1",
		RequestId:      "44444444-4444-4444-8444-444444444444",
		TenantId:       contracts.TenantId(c.TenantID),
		NodeId:         contracts.NodeId(c.NodeID),
		RecoveryEpoch:  c.Epoch,
		Scope:          "build-session",
		BuildSessionId: &session,
		ReasonCode:     "VERIFY-0022",
		RequestedAt:    contracts.Timestamp("2026-10-02T00:00:00Z"),
	}
}

func rawQuarantine(t *testing.T, request contracts.BuildQuarantineRequest) []byte {
	t.Helper()
	raw, err := json.Marshal(request)
	if err != nil {
		t.Fatal(err)
	}
	return raw
}

func TestQuarantineIsDurableIdempotentAndPrivate(t *testing.T) {
	c, _, _ := fixture(t)
	j := journalFor(t, c)
	runner := New(c, j, &fakeEngine{})
	request := quarantineRequest(c)
	first, err := runner.Quarantine(context.Background(), rawQuarantine(t, request))
	if err != nil || !first.Durable || first.Replayed {
		t.Fatal("first quarantine was not durably recorded", err)
	}
	info, err := os.Lstat(filepath.Join(j.root, request.RequestId+".build-quarantine"))
	if err != nil || !info.Mode().IsRegular() || info.Mode().Perm()&0077 != 0 {
		t.Fatal("quarantine journal entry is not private", err)
	}
	if temporary, err := filepath.Glob(filepath.Join(j.root, ".quarantine-*")); err != nil || len(temporary) != 0 {
		t.Fatal("atomic quarantine write left a temporary entry", temporary, err)
	}
	second, err := runner.Quarantine(context.Background(), rawQuarantine(t, request))
	if err != nil || !second.Replayed || second.RecordedAt != first.RecordedAt {
		t.Fatal("exact replay did not return the original receipt", err)
	}
	request.ReasonCode = "RES-0006"
	if _, err = runner.Quarantine(context.Background(), rawQuarantine(t, request)); err == nil {
		t.Fatal("conflicting reuse of quarantine requestId was accepted")
	}
}

func TestConcurrentQuarantineCreatesOneReceiptAndReplaysTheRest(t *testing.T) {
	c, _, _ := fixture(t)
	runner := New(c, journalFor(t, c), &fakeEngine{})
	raw := rawQuarantine(t, quarantineRequest(c))
	const count = 8
	var wg sync.WaitGroup
	receipts := make(chan contracts.BuildQuarantineReceipt, count)
	errs := make(chan error, count)
	for i := 0; i < count; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			receipt, err := runner.Quarantine(context.Background(), raw)
			receipts <- receipt
			errs <- err
		}()
	}
	wg.Wait()
	close(receipts)
	close(errs)
	for err := range errs {
		if err != nil {
			t.Fatal(err)
		}
	}
	replayed := 0
	var recordedAt contracts.Timestamp
	for receipt := range receipts {
		if receipt.Replayed {
			replayed++
		}
		if recordedAt == "" {
			recordedAt = receipt.RecordedAt
		} else if receipt.RecordedAt != recordedAt {
			t.Fatal("replay changed recordedAt")
		}
	}
	if replayed != count-1 {
		t.Fatalf("got %d replayed receipts, want %d", replayed, count-1)
	}
}

func TestQuarantineRejectsWrongIdentityAndInvalidShapeWithoutARecord(t *testing.T) {
	c, _, _ := fixture(t)
	j := journalFor(t, c)
	runner := New(c, j, &fakeEngine{})
	request := quarantineRequest(c)
	request.NodeId = contracts.NodeId("nod_11111111111111111111111111")
	if _, err := runner.Quarantine(context.Background(), rawQuarantine(t, request)); err == nil {
		t.Fatal("wrong node identity accepted")
	}
	if _, err := os.Lstat(filepath.Join(j.root, request.RequestId+".build-quarantine")); !os.IsNotExist(err) {
		t.Fatal("rejected identity left a journal entry")
	}
	bad := append(rawQuarantine(t, quarantineRequest(c))[:len(rawQuarantine(t, quarantineRequest(c)))-1], []byte(`,"extra":true}`)...)
	if _, err := runner.Quarantine(context.Background(), bad); err == nil {
		t.Fatal("unknown request field accepted")
	}
}
