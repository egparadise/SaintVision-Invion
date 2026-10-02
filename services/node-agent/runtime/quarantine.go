package runtime

import (
	"context"
	"encoding/json"
	"errors"
	contracts "github.com/egparadise/SaintVision-Invion/packages/contracts-go"
	"github.com/egparadise/SaintVision-Invion/services/node-agent/internal/wire"
	"time"
)

// Quarantine durably records a reconciliation obligation before acknowledging
// it to the control plane. It does not claim that the affected build or Node has
// already been repaired; exact replay is the read/reconciliation path.
func (r *Runner) Quarantine(ctx context.Context, raw []byte) (contracts.BuildQuarantineReceipt, error) {
	if err := wire.Validate("BuildQuarantineRequest", raw); err != nil {
		return contracts.BuildQuarantineReceipt{}, err
	}
	var request contracts.BuildQuarantineRequest
	if err := json.Unmarshal(raw, &request); err != nil {
		return contracts.BuildQuarantineReceipt{}, errors.New("NODE-0003: invalid quarantine request")
	}
	if string(request.TenantId) != r.config.TenantID || string(request.NodeId) != r.config.NodeID || request.RecoveryEpoch != r.config.Epoch {
		return contracts.BuildQuarantineReceipt{}, errors.New("NODE-0032: quarantine request identity differs")
	}
	if err := ctx.Err(); err != nil {
		return contracts.BuildQuarantineReceipt{}, errors.New("NODE-0016: quarantine request cancelled")
	}
	r.quarantineMutex.Lock()
	defer r.quarantineMutex.Unlock()
	if err := ctx.Err(); err != nil {
		return contracts.BuildQuarantineReceipt{}, errors.New("NODE-0016: quarantine request cancelled")
	}
	receipt, _, err := r.journal.RecordQuarantine(
		request,
		contracts.Timestamp(time.Now().UTC().Format(time.RFC3339Nano)),
	)
	return receipt, err
}
