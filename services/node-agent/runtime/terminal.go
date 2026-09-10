package runtime

import (
	"bytes"
	"context"
	"encoding/base64"
	"encoding/binary"
	"encoding/json"
	"errors"
	contracts "github.com/egparadise/SaintVision-Invion/packages/contracts-go"
	"github.com/egparadise/SaintVision-Invion/services/node-agent/internal/wire"
	"io"
	"net/http"
	"time"
)

// Terminal never starts/restarts a workload. Only the currently active signed
// command can reach its already running image-owned helper.
func (r *Runner) Terminal(ctx context.Context, raw []byte) (contracts.NodeTerminalResult, error) {
	var in contracts.NodeTerminalInput
	var zero contracts.NodeTerminalResult
	if wire.Validate("NodeTerminalInput", raw) != nil || json.Unmarshal(raw, &in) != nil {
		return zero, errors.New("NODE-0090: invalid terminal input")
	}
	envelope, _ := json.Marshal(in.Permit)
	permit, err := Verify(envelope, r.config)
	if err != nil || permit.Data.Launch.Terminal == nil {
		return zero, errors.New("NODE-0090: explicit terminal permit required")
	}
	if _, err = permit.Budget(time.Now()); err != nil {
		return zero, err
	}
	r.activeMutex.Lock()
	active := r.activeHash == permit.Hash && r.activeCancel != nil
	r.activeMutex.Unlock()
	if !active {
		return zero, errors.New("NODE-0090: original execution is not active")
	}
	engine, ok := r.engine.(interface {
		Terminal(context.Context, Record, contracts.TerminalFrameInput) (contracts.NodeTerminalResult, error)
	})
	if !ok {
		return zero, errors.New("NODE-0090: terminal engine unavailable")
	}
	record := Record{Hash: permit.Hash, Claim: permit.Data.Claim, Allocations: permit.Data.Allocations, Name: containerName(permit.Data.Claim)}
	result, err := engine.Terminal(ctx, record, in.Frame)
	if err != nil {
		return zero, err
	}
	if result.CommandId != record.Claim.CommandId || result.SessionId != permit.Data.Launch.Terminal.SessionId || result.Nonce != in.Frame.Nonce {
		return zero, errors.New("NODE-0090: terminal response scope differs")
	}
	return result, nil
}

func (d *Docker) Terminal(ctx context.Context, r Record, frame contracts.TerminalFrameInput) (contracts.NodeTerminalResult, error) {
	var zero contracts.NodeTerminalResult
	state, err := d.Inspect(ctx, r.Name, r)
	if err != nil || !state.Running || state.Restarting {
		return zero, errors.New("NODE-0090: running owned terminal required")
	}
	raw, _ := json.Marshal(frame)
	config := map[string]any{"AttachStdout": true, "AttachStderr": false, "AttachStdin": false, "Tty": false, "Privileged": false, "User": "65532:65532",
		"Cmd": []string{"/inv-supervisor", "--terminal-frame"}, "Env": []string{"INV_TERMINAL_FRAME=" + base64.StdEncoding.EncodeToString(raw)}}
	var created struct {
		ID string `json:"Id"`
	}
	if err = d.request(ctx, "POST", "/containers/"+state.ID+"/exec", config, &created); err != nil {
		return zero, err
	}
	if !hexID.MatchString(created.ID) {
		return zero, errors.New("NODE-0090: invalid terminal helper")
	}
	req, err := http.NewRequestWithContext(ctx, "POST", "http://docker/v1.45/exec/"+created.ID+"/start", bytes.NewBufferString(`{"Detach":false,"Tty":false}`))
	if err != nil {
		return zero, err
	}
	req.Header.Set("Content-Type", "application/json")
	response, err := d.client.Do(req)
	if err != nil {
		return zero, ErrEngineUnavailable
	}
	defer response.Body.Close()
	if response.StatusCode != 200 {
		return zero, errors.New("NODE-0090: terminal helper failed")
	}
	reader := io.LimitReader(response.Body, 20001)
	var data []byte
	for {
		header := make([]byte, 8)
		n, err := io.ReadFull(reader, header)
		if err == io.EOF && n == 0 {
			break
		}
		if err != nil || header[0] != 1 || header[1] != 0 || header[2] != 0 || header[3] != 0 {
			return zero, errors.New("NODE-0090: invalid helper output")
		}
		size := int(binary.BigEndian.Uint32(header[4:]))
		if size > 16384-len(data) {
			return zero, errors.New("NODE-0090: helper output exceeded")
		}
		part := make([]byte, size)
		if _, err = io.ReadFull(reader, part); err != nil {
			return zero, errors.New("NODE-0090: incomplete helper output")
		}
		data = append(data, part...)
	}
	if wire.Validate("NodeTerminalResult", data) != nil || json.Unmarshal(data, &zero) != nil {
		return contracts.NodeTerminalResult{}, errors.New("NODE-0090: invalid terminal result")
	}
	return zero, nil
}
