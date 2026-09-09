//go:build linux

package runtime

import (
	"context"
	"encoding/json"
	"errors"
	contracts "github.com/egparadise/SaintVision-Invion/packages/contracts-go"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"
)

type fakeEngine struct {
	state                               State
	creates, starts, stops, removes     int
	lostStart, absent, removeFail, wait bool
}

func (e *fakeEngine) Create(_ context.Context, r Record, p contracts.SandboxLaunchSpec) (string, error) {
	e.creates++
	if e.absent {
		return "", errors.New("lost create")
	}
	e.state = State{ID: strings.Repeat("a", 64), Status: "created"}
	return e.state.ID, nil
}
func (e *fakeEngine) Start(_ context.Context, id string) error {
	e.starts++
	e.state.StartedAt = time.Now().UTC().Format(time.RFC3339Nano)
	if e.wait || e.lostStart {
		e.state.Running = true
		e.state.PID = 1
		e.state.Status = "running"
	} else {
		e.state.Status = "exited"
	}
	if e.lostStart {
		return errors.New("lost start ACK")
	}
	return nil
}
func (e *fakeEngine) Inspect(_ context.Context, _ string, _ Record) (State, error) {
	if e.absent || e.state.ID == "" {
		return State{}, ErrAbsent
	}
	return e.state, nil
}
func (e *fakeEngine) Stop(_ context.Context, _ string) error {
	e.stops++
	e.state.Running = false
	e.state.PID = 0
	e.state.Status = "exited"
	e.state.ExitCode = 137
	return nil
}
func (e *fakeEngine) Remove(_ context.Context, _ string, _ Record) error {
	e.removes++
	if e.removeFail {
		return errors.New("late start still running")
	}
	e.state = State{}
	return nil
}
func journalFor(t *testing.T, c Config) *Journal {
	t.Helper()
	j, err := OpenJournal(filepath.Join(t.TempDir(), "journal"), c)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = j.Close() })
	return j
}
func TestConcurrentDuplicateAndProcessRestart(t *testing.T) {
	c, p, k := fixture(t)
	j := journalFor(t, c)
	e := &fakeEngine{}
	r := New(c, j, e)
	data := signed(t, p, k)
	var wg sync.WaitGroup
	results := make(chan Result, 8)
	errs := make(chan error, 8)
	for i := 0; i < 8; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			result, err := r.Execute(context.Background(), data)
			results <- result
			errs <- err
		}()
	}
	wg.Wait()
	close(results)
	close(errs)
	for err := range errs {
		if err != nil {
			t.Fatal(err)
		}
	}
	duplicates := 0
	receipt := ""
	for r := range results {
		if r.Duplicate {
			duplicates++
		}
		if receipt == "" {
			receipt = r.Receipt.ReceiptId
		}
		if r.Receipt.ReceiptId != receipt {
			t.Fatal("receipt differs")
		}
	}
	if duplicates != 7 || e.starts != 1 || e.removes != 1 {
		t.Fatal("duplicate execution")
	}
	_ = j.Close()
	j2, err := OpenJournal(j.root, c)
	if err != nil {
		t.Fatal(err)
	}
	defer j2.Close()
	again, err := New(c, j2, &fakeEngine{absent: true}).Execute(context.Background(), data)
	if err != nil || !again.Duplicate || again.Receipt.ReceiptId != receipt {
		t.Fatal("restart lost deduplication", err)
	}
}
func TestLostStartACKStopsWithoutRestart(t *testing.T) {
	c, p, k := fixture(t)
	j := journalFor(t, c)
	e := &fakeEngine{lostStart: true}
	r := New(c, j, e)
	data := signed(t, p, k)
	result, err := r.Execute(context.Background(), data)
	if err != nil || result.Receipt == nil || e.stops != 1 || !result.Receipt.ProcessStarted {
		t.Fatal("stop missing", err)
	}
	_, err = r.Execute(context.Background(), data)
	if err != nil || e.starts != 1 {
		t.Fatal("lost ACK caused restart", err)
	}
}
func TestAmbiguousCreateNeverRetriesOrAcknowledges(t *testing.T) {
	c, p, k := fixture(t)
	j := journalFor(t, c)
	e := &fakeEngine{absent: true}
	r := New(c, j, e)
	data := signed(t, p, k)
	for i := 0; i < 2; i++ {
		result, err := r.Execute(context.Background(), data)
		if err == nil || result.Receipt != nil {
			t.Fatal("unknown execution acknowledged")
		}
	}
	if e.creates != 1 || e.starts != 0 {
		t.Fatal("ambiguous create retried")
	}
}
func TestStopObservationWithoutRemovalCannotRelease(t *testing.T) {
	c, p, k := fixture(t)
	j := journalFor(t, c)
	e := &fakeEngine{removeFail: true}
	result, err := New(c, j, e).Execute(context.Background(), signed(t, p, k))
	if err == nil || result.Receipt != nil {
		t.Fatal("late start race released allocation")
	}
	_, receipt, err := j.Get(string(p.Claim.CommandId))
	if err != nil || receipt != nil {
		t.Fatal("receipt persisted before removal")
	}
}
func TestCrashIntentRecoveryNeverStarts(t *testing.T) {
	c, p, k := fixture(t)
	j := journalFor(t, c)
	permit, err := Verify(signed(t, p, k), c)
	if err != nil {
		t.Fatal(err)
	}
	_, err = j.Begin(permit, containerName(p.Claim))
	if err != nil {
		t.Fatal(err)
	}
	e := &fakeEngine{state: State{ID: strings.Repeat("a", 64), Running: true, PID: 1, Status: "running", StartedAt: time.Now().UTC().Format(time.RFC3339Nano)}}
	results, err := New(c, j, e).Recover(context.Background())
	if err != nil || len(results) != 1 || e.starts != 0 || e.stops != 1 || e.removes != 1 {
		t.Fatal("unsafe crash recovery", err)
	}
}
func TestJournalExclusiveLockAndEpochPin(t *testing.T) {
	c, _, _ := fixture(t)
	j := journalFor(t, c)
	if second, err := OpenJournal(j.root, c); err == nil {
		second.Close()
		t.Fatal("second worker admitted")
	}
	_ = j.Close()
	c.Epoch = uuid()
	if second, err := OpenJournal(j.root, c); err == nil {
		second.Close()
		t.Fatal("epoch reset admitted")
	}
}
func TestCorruptIntentBlocksFurtherExecution(t *testing.T) {
	c, p, k := fixture(t)
	j := journalFor(t, c)
	if err := os.WriteFile(filepath.Join(j.root, uuid()+".intent"), []byte("{"), 0600); err != nil {
		t.Fatal(err)
	}
	e := &fakeEngine{}
	if _, err := New(c, j, e).Execute(context.Background(), signed(t, p, k)); err == nil || e.creates != 0 {
		t.Fatal("ignored corrupt pending intent")
	}
}
func TestPerLeaseHighWaterRejectsStaleOrReusedFence(t *testing.T) {
	for _, token := range []string{"1", "2"} {
		t.Run(token, func(t *testing.T) {
			c, p, k := fixture(t)
			j := journalFor(t, c)
			p.Allocations[0].Lease.FencingToken = c.Epoch + ":2"
			first, _ := Verify(signed(t, p, k), c)
			if _, err := j.Begin(first, containerName(p.Claim)); err != nil {
				t.Fatal(err)
			}
			p.Claim.CommandId = contracts.CommandId(uuid())
			p.Allocations[0].Lease.FencingToken = c.Epoch + ":" + token
			next, _ := Verify(signed(t, p, k), c)
			if _, err := j.Begin(next, containerName(p.Claim)); err == nil {
				t.Fatal("stale fence accepted")
			}
		})
	}
}
func TestTimeoutAndCancellationRequirePhysicalStop(t *testing.T) {
	for _, cancelNow := range []bool{false, true} {
		name := "timeout"
		if cancelNow {
			name = "cancelled"
		}
		t.Run(name, func(t *testing.T) {
			c, p, k := fixture(t)
			p.Launch.TimeoutSeconds = 1
			j := journalFor(t, c)
			e := &fakeEngine{wait: true}
			ctx, cancel := context.WithCancel(context.Background())
			defer cancel()
			if cancelNow {
				time.AfterFunc(100*time.Millisecond, cancel)
			}
			result, err := New(c, j, e).Execute(ctx, signed(t, p, k))
			if err != nil || result.Receipt == nil || result.Receipt.Reason != name || e.stops != 1 || e.removes != 1 {
				t.Fatal("stop not verified", err)
			}
		})
	}
}

func TestCorruptReceiptCannotBeReplayed(t *testing.T) {
	c, p, k := fixture(t)
	j := journalFor(t, c)
	r := New(c, j, &fakeEngine{})
	data := signed(t, p, k)
	result, err := r.Execute(context.Background(), data)
	if err != nil {
		t.Fatal(err)
	}
	result.Receipt.NodeId = contracts.NodeId("nod_" + strings.Repeat("1", 26))
	raw, _ := json.Marshal(result.Receipt)
	if err := os.WriteFile(filepath.Join(j.root, string(p.Claim.CommandId)+".receipt"), raw, 0600); err != nil {
		t.Fatal(err)
	}
	if result, err := r.Execute(context.Background(), data); err == nil || result.Receipt != nil {
		t.Fatal("foreign receipt replayed")
	}
}

func TestObservationNeverCreatesAnUnseenCommand(t *testing.T) {
	c, p, k := fixture(t)
	j := journalFor(t, c)
	engine := &fakeEngine{}
	r := New(c, j, engine)
	if result, err := r.Observe(context.Background(), signed(t, p, k)); err == nil || result.Receipt != nil || engine.creates != 0 {
		t.Fatal("observation created execution")
	}
}
func TestPeerPolicyFloorSurvivesRestart(t *testing.T) {
	c, _, _ := fixture(t)
	j := journalFor(t, c)
	if err := j.PinPeerPolicy(1, strings.Repeat("a", 64)); err != nil {
		t.Fatal(err)
	}
	if err := j.PinPeerPolicy(2, strings.Repeat("b", 64)); err != nil {
		t.Fatal(err)
	}
	_ = j.Close()
	next, err := OpenJournal(j.root, c)
	if err != nil {
		t.Fatal(err)
	}
	defer next.Close()
	if next.PinPeerPolicy(1, strings.Repeat("a", 64)) == nil || next.PinPeerPolicy(2, strings.Repeat("c", 64)) == nil {
		t.Fatal("policy floor reset after restart")
	}
	if next.PinPeerPolicy(2, strings.Repeat("b", 64)) != nil || next.PinPeerPolicy(3, strings.Repeat("c", 64)) != nil {
		t.Fatal("forward policy update failed")
	}
}
