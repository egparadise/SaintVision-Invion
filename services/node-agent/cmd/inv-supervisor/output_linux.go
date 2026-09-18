//go:build linux

package main

import (
	"encoding/json"
	contracts "github.com/egparadise/SaintVision-Invion/packages/contracts-go"
	"os"
	"sync"
)

// Drain every write, retain bounded bytes, and emit one private artifact.
type outputBuffer struct {
	mutex     sync.Mutex
	data      []byte
	truncated bool
}

func emitWorkspaceOutput(stdout, stderr *outputBuffer, input *contracts.WorkspaceInput, snapshot contracts.WorkspaceSnapshot) int {
	stdout.mutex.Lock()
	defer stdout.mutex.Unlock()
	stderr.mutex.Lock()
	defer stderr.mutex.Unlock()
	if stdout.truncated || stderr.truncated {
		return 122
	}
	workspace := map[string]any{"stepId": input.StepId, "inputSha256": input.Sha256, "snapshot": snapshot}
	if input.StartId != nil {
		workspace["startId"] = *input.StartId
	} else if input.ResumeId != nil {
		workspace["resumeId"] = *input.ResumeId
	} else {
		return 122
	}
	artifact := map[string]any{"stdout": append([]byte{}, stdout.data...), "stderr": append([]byte{}, stderr.data...), "truncated": false,
		"workspace": workspace}
	if json.NewEncoder(os.Stdout).Encode(artifact) != nil {
		return 122
	}
	return 0
}

func (b *outputBuffer) Write(p []byte) (int, error) {
	b.mutex.Lock()
	defer b.mutex.Unlock()
	n := len(p)
	remaining := 65536 - len(b.data)
	if len(p) > remaining {
		p = p[:remaining]
		b.truncated = true
	}
	b.data = append(b.data, p...)
	return n, nil
}
func emitOutput(stdout, stderr *outputBuffer, code int) int {
	stdout.mutex.Lock()
	defer stdout.mutex.Unlock()
	stderr.mutex.Lock()
	defer stderr.mutex.Unlock()
	truncated := stdout.truncated || stderr.truncated
	artifact := struct {
		Stdout    []byte `json:"stdout"`
		Stderr    []byte `json:"stderr"`
		Truncated bool   `json:"truncated"`
	}{append([]byte{}, stdout.data...), append([]byte{}, stderr.data...), truncated}
	if err := json.NewEncoder(os.Stdout).Encode(artifact); err != nil {
		return 122
	}
	if truncated {
		return 122
	}
	return code
}
