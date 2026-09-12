package wire

import (
	"bytes"
	_ "embed"
	"encoding/json"
	"errors"
	js "github.com/santhosh-tekuri/jsonschema/v6"
	"io"
	"sync"
)

//go:embed core.schema.json
var bundle []byte
var once sync.Once
var schemas map[string]*js.Schema
var initErr error

const schemaURL = "https://saintvision.ai/contracts/v1alpha1/core.schema.json"

func initialize() {
	compiler := js.NewCompiler()
	compiler.AssertFormat()
	var document any
	document, initErr = js.UnmarshalJSON(bytes.NewReader(bundle))
	if initErr != nil {
		return
	}
	initErr = compiler.AddResource(schemaURL, document)
	if initErr != nil {
		return
	}
	schemas = make(map[string]*js.Schema)
	for _, name := range []string{"SignedNodePermit", "NodeExecutionPermit", "NodeStopReceipt", "NodeExecutionResult", "NodePeerPolicy", "NodeProbeInput", "NodeProbeResult", "NodeResourceSnapshot", "NodeChunkInput", "NodeChunkResult", "WorkspaceSnapshot", "CommandId", "TerminalSpec", "TerminalFrameInput", "NodeTerminalInput", "NodeTerminalResult", "NodeStorageChallenge", "NodeStorageSampleInput", "NodeStorageSignedSample", "NodeStorageRootConfig"} {
		schemas[name], initErr = compiler.Compile(schemaURL + "#/$defs/" + name)
		if initErr != nil {
			return
		}
	}
}

// Reject duplicate keys before a parser can discard conflicting signed content.
func StrictJSON(data []byte) error {
	if len(data) > 2*1024*1024 {
		return errors.New("NODE-0003: JSON exceeds limit")
	}
	dec := json.NewDecoder(bytes.NewReader(data))
	dec.UseNumber()
	var value func(int) error
	value = func(depth int) error {
		if depth > 64 {
			return errors.New("NODE-0003: JSON nesting exceeds limit")
		}
		token, err := dec.Token()
		if err != nil {
			return err
		}
		delimiter, ok := token.(json.Delim)
		if !ok {
			return nil
		}
		if delimiter == '{' {
			seen := map[string]bool{}
			for dec.More() {
				key, err := dec.Token()
				if err != nil {
					return err
				}
				text, ok := key.(string)
				if !ok || seen[text] {
					return errors.New("NODE-0003: duplicate JSON key")
				}
				seen[text] = true
				if err := value(depth + 1); err != nil {
					return err
				}
			}
			close, err := dec.Token()
			if err != nil || close != json.Delim('}') {
				return errors.New("NODE-0003: invalid object")
			}
			return nil
		}
		if delimiter == '[' {
			for dec.More() {
				if err := value(depth + 1); err != nil {
					return err
				}
			}
			close, err := dec.Token()
			if err != nil || close != json.Delim(']') {
				return errors.New("NODE-0003: invalid array")
			}
			return nil
		}
		return errors.New("NODE-0003: invalid JSON delimiter")
	}
	if err := value(1); err != nil {
		return errors.New("NODE-0003: invalid JSON")
	}
	if _, err := dec.Token(); err != io.EOF {
		return errors.New("NODE-0003: trailing JSON")
	}
	return nil
}

func Validate(name string, data []byte) error {
	if err := StrictJSON(data); err != nil {
		return err
	}
	once.Do(initialize)
	if initErr != nil || schemas[name] == nil {
		return errors.New("NODE-0004: schema unavailable")
	}
	value, err := js.UnmarshalJSON(bytes.NewReader(data))
	if err != nil {
		return errors.New("NODE-0003: invalid JSON")
	}
	if err = schemas[name].Validate(value); err != nil {
		return errors.New("NODE-0004: contract rejected")
	}
	return nil
}
