package runtime

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	contracts "github.com/egparadise/SaintVision-Invion/packages/contracts-go"
	"github.com/egparadise/SaintVision-Invion/services/node-agent/internal/wire"
	"sync"
	"time"
)

type Result struct {
	Duplicate      bool                       `json:"duplicate"`
	Receipt        *contracts.NodeStopReceipt `json:"receipt"`
	CleanupPending bool                       `json:"cleanupPending"`
}
type Runner struct {
	config  Config
	journal *Journal
	engine  Engine
	mutex   sync.Mutex
}

func New(config Config, journal *Journal, engine Engine) *Runner {
	return &Runner{config: config, journal: journal, engine: engine}
}
func containerName(claim contracts.ExecutionClaim) string {
	bytes := sha256.Sum256([]byte(string(claim.TenantId) + ":" + string(claim.NodeId) + ":" + string(claim.CommandId)))
	return "inv-" + hex.EncodeToString(bytes[:24])
}
func uuid() string {
	var b [16]byte
	if _, err := rand.Read(b[:]); err != nil {
		panic("random source unavailable")
	}
	b[6] = (b[6] & 15) | 64
	b[8] = (b[8] & 63) | 128
	return fmt.Sprintf("%x-%x-%x-%x-%x", b[:4], b[4:6], b[6:8], b[8:10], b[10:])
}

func (r *Runner) Execute(ctx context.Context, envelope []byte) (Result, error) {
	permit, err := Verify(envelope, r.config)
	if err != nil {
		return Result{}, err
	}
	r.mutex.Lock()
	defer r.mutex.Unlock()
	prior, receipt, err := r.journal.Get(string(permit.Data.Claim.CommandId))
	if err != nil {
		return Result{}, err
	}
	if prior != nil {
		if prior.Hash != permit.Hash {
			return Result{}, errors.New("NODE-0015: command content differs")
		}
		if receipt != nil {
			return Result{Duplicate: true, Receipt: receipt}, nil
		}
		result, err := r.reconcile(*prior, "recovered")
		result.Duplicate = true
		return result, err
	}
	pending, err := r.journal.Pending()
	if err != nil {
		return Result{}, err
	}
	for _, record := range pending {
		if _, err = r.reconcile(record, "recovered"); err != nil {
			return Result{}, err
		}
	}
	admittedAt := time.Now()
	budget, err := permit.Budget(admittedAt)
	if err != nil {
		return Result{}, err
	}
	if err = ctx.Err(); err != nil {
		return Result{}, errors.New("NODE-0016: caller cancelled before start")
	}
	record, err := r.journal.Begin(permit, containerName(permit.Data.Claim))
	if err != nil {
		return Result{}, err
	}
	// Context deadline carries Go's monotonic clock through create, start and wait.
	execution, cancel := context.WithDeadline(ctx, admittedAt.Add(budget))
	defer cancel()
	id, err := r.engine.Create(execution, *record, permit.Data.Launch)
	if err == nil && execution.Err() == nil {
		err = r.engine.Start(execution, id)
	}
	if err != nil || execution.Err() != nil {
		return r.reconcile(*record, reason(execution))
	}
	ticker := time.NewTicker(50 * time.Millisecond)
	defer ticker.Stop()
	for {
		state, inspectErr := r.engine.Inspect(execution, id, *record)
		if inspectErr == nil && stopped(state) {
			return r.finish(*record, state, "exited")
		}
		if inspectErr != nil {
			return r.reconcile(*record, reason(execution))
		}
		select {
		case <-execution.Done():
			return r.reconcile(*record, reason(execution))
		case <-ticker.C:
		}
	}
}
func reason(ctx context.Context) string {
	if errors.Is(ctx.Err(), context.DeadlineExceeded) {
		return "timeout"
	}
	if ctx.Err() != nil {
		return "cancelled"
	}
	return "recovered"
}
func (r *Runner) Recover(ctx context.Context) ([]Result, error) {
	r.mutex.Lock()
	defer r.mutex.Unlock()
	pending, err := r.journal.Pending()
	if err != nil {
		return nil, err
	}
	results := []Result{}
	for _, record := range pending {
		if ctx.Err() != nil {
			return results, ctx.Err()
		}
		result, err := r.reconcile(record, "recovered")
		if err != nil {
			return results, err
		}
		results = append(results, result)
	}
	return results, nil
}
func (r *Runner) reconcile(record Record, why string) (Result, error) {
	// Cleanup gets its own bounded context after caller cancellation. A timeout or
	// absent container does not prove the original create/start had no effect.
	ctx, cancel := context.WithTimeout(context.Background(), 4*time.Second)
	defer cancel()
	state, err := r.engine.Inspect(ctx, record.Name, record)
	if err != nil {
		return Result{}, errors.New("NODE-0027: execution uncertain; no stop receipt or automatic retry")
	}
	if !stopped(state) {
		_ = r.engine.Stop(ctx, state.ID)
		ticker := time.NewTicker(50 * time.Millisecond)
		defer ticker.Stop()
		for {
			state, err = r.engine.Inspect(ctx, record.Name, record)
			if err != nil {
				return Result{}, errors.New("NODE-0027: stop not verified")
			}
			if stopped(state) {
				break
			}
			select {
			case <-ctx.Done():
				return Result{}, errors.New("NODE-0027: stop deadline exceeded")
			case <-ticker.C:
			}
		}
	}
	return r.finish(record, state, why)
}
func (r *Runner) finish(record Record, state State, why string) (Result, error) {
	if !stopped(state) {
		return Result{}, errors.New("NODE-0027: stop not verified")
	}
	started, err := time.Parse(time.RFC3339Nano, state.StartedAt)
	didStart := err == nil && started.Year() > 2000
	exitCode := int64(state.ExitCode)
	if !didStart {
		exitCode = -1
	}
	claim := record.Claim
	receipt := contracts.NodeStopReceipt{ReceiptId: uuid(), ClaimId: claim.ClaimId, CommandId: claim.CommandId, TenantId: claim.TenantId, ProjectId: claim.ProjectId,
		RunId: claim.RunId, NodeId: claim.NodeId, RecoveryEpoch: claim.RecoveryEpoch, PlanDigest: claim.PlanDigest, ContainerId: state.ID, Stopped: true, ProcessStarted: didStart,
		ExitCode: exitCode, Reason: why, FinishedAt: contracts.Timestamp(time.Now().UTC().Format(time.RFC3339Nano)), Allocations: record.Allocations}
	raw, _ := json.Marshal(receipt)
	if err := wire.Validate("NodeStopReceipt", raw); err != nil {
		return Result{}, err
	}
	// Remove the confirmed stopped container before acknowledging. This also
	// fences a delayed Docker start request: a removed ID cannot start later.
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	if err := r.engine.Remove(ctx, state.ID, record); err != nil {
		return Result{}, errors.New("NODE-0027: final removal unconfirmed; no receipt")
	}
	if err := r.journal.Save(receipt); err != nil {
		return Result{}, errors.New("NODE-0013: receipt persistence failed")
	}
	return Result{Receipt: &receipt}, nil

}
