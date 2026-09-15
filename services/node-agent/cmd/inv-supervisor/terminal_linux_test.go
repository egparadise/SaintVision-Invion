//go:build linux

package main

import (
	"encoding/base64"
	contracts "github.com/egparadise/SaintVision-Invion/packages/contracts-go"
	"io"
	"os"
	"testing"
)

// These regression sources are prepared for the later test phase.
func TestTerminalSuccessfulInputReplayDoesNotWriteTwice(t *testing.T) {
	reader, writer, err := os.Pipe()
	if err != nil {
		t.Fatal(err)
	}
	defer reader.Close()
	p := &terminalPTY{master: writer, spec: contracts.TerminalSpec{MaxInputBytes: 8, MaxOutputBytes: 16}}
	frame := contracts.TerminalFrameInput{Sequence: 1, Operation: "input", DataBase64: base64.StdEncoding.EncodeToString([]byte("abc")), Rows: 24, Columns: 80, Nonce: "a"}
	first, err := p.frame(frame)
	if err != nil {
		t.Fatal(err)
	}
	replay, err := p.frame(frame)
	if err != nil || *first != *replay {
		t.Fatal("successful replay changed result")
	}
	writer.Close()
	data, err := io.ReadAll(reader)
	if err != nil || string(data) != "abc" || p.inputBytes != 3 {
		t.Fatal("input replay wrote twice")
	}
	frame.Nonce = "different"
	if _, err = p.frame(frame); err == nil {
		t.Fatal("sequence reuse with different content accepted")
	}
}

func TestTerminalPollDoesNotConsumeSequenceAndBoundsCursor(t *testing.T) {
	p := &terminalPTY{output: []byte("hello"), sequence: 3}
	f := contracts.TerminalFrameInput{Operation: "poll", Cursor: 2}
	result, err := p.frame(f)
	if err != nil || result.Sequence != 3 || result.Cursor != 5 || result.DataBase64 != "bGxv" {
		t.Fatal("poll changed input order or output")
	}
	f.Cursor = 6
	if _, err = p.frame(f); err == nil {
		t.Fatal("future cursor accepted")
	}
	f.Cursor = 0
	f.Sequence = 1
	if _, err = p.frame(f); err == nil {
		t.Fatal("poll consumed sequence")
	}
}

func TestTerminalFailedInputPoisonsSessionWithoutReplay(t *testing.T) {
	reader, writer, err := os.Pipe()
	if err != nil {
		t.Fatal(err)
	}
	reader.Close()
	writer.Close()
	p := &terminalPTY{master: writer, spec: contracts.TerminalSpec{MaxInputBytes: 8}}
	f := contracts.TerminalFrameInput{Sequence: 1, Operation: "input", DataBase64: "YQ=="}
	if _, err = p.frame(f); err == nil || !p.poisoned || p.sequence != 1 {
		t.Fatal("uncertain write was not fenced")
	}
	if _, err = p.frame(f); err == nil {
		t.Fatal("uncertain input was replayed")
	}
}
