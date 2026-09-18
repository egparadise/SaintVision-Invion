package runtime

import (
	"context"
	"errors"
	"testing"
)

type cleanupEngine struct {
	Engine
	errors []error
	calls  int
	state  State
}

func (e *cleanupEngine) Inspect(ctx context.Context, identity string, record Record) (State, error) {
	e.calls++
	if e.calls <= len(e.errors) {
		return State{}, e.errors[e.calls-1]
	}
	return e.state, nil
}

func TestCleanupObservationRequiresFreshPhysicalEvidence(t *testing.T) {
	foreign := errors.New("NODE-0025: container ownership differs")
	malformed := errors.New("NODE-0022: invalid engine response")
	for _, tc := range []struct {
		name     string
		failures []error
		calls    int
		verified bool
		cancel   bool
	}{
		{"unavailable_then_stopped", []error{ErrEngineUnavailable, ErrEngineUnavailable}, 3, true, false},
		{"late_create_visible", []error{ErrAbsent, ErrAbsent}, 3, true, false},
		{"persistent_unavailable", []error{ErrEngineUnavailable, ErrEngineUnavailable, ErrEngineUnavailable}, 3, false, false},
		{"persistent_absence", []error{ErrAbsent, ErrAbsent, ErrAbsent}, 3, false, false},
		{"foreign_owner", []error{foreign}, 1, false, false},
		{"malformed_response", []error{malformed}, 1, false, false},
		{"cleanup_deadline", []error{ErrEngineUnavailable}, 1, false, true},
	} {
		t.Run(tc.name, func(t *testing.T) {
			engine := &cleanupEngine{errors: tc.failures, state: State{ID: "owned", Status: "exited", ExitCode: 137}}
			ctx, cancel := context.WithCancel(context.Background())
			defer cancel()
			if tc.cancel {
				cancel()
			}
			state, err := (&Runner{engine: engine}).observeCleanup(ctx, "owned-name", Record{})
			if engine.calls != tc.calls || (err == nil) != tc.verified || (tc.verified && !stopped(state)) {
				t.Fatalf("calls=%d state=%+v err=%v", engine.calls, state, err)
			}
			// All other Engine methods are nil: any execution/retry or receipt
			// side effect would panic instead of turning observation into proof.
		})
	}
}
