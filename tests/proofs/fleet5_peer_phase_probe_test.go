// This file is copied into the ACTUAL node-agent transport package by the
// opt-in Linux proof runner. It is never a substitute runtime/module.
package transport

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	goruntime "runtime"
	"strings"
	"testing"

	node "github.com/egparadise/SaintVision-Invion/services/node-agent/runtime"
)

func TestFleet5GeneratedPeerPoliciesCompleteTwoNormalCycles(t *testing.T) {
	if goruntime.GOOS != "linux" {
		t.Fatal("invalid proof: actual Linux journal locking/modes required")
	}
	dir, report := os.Getenv("FLEET5_PEER_PROOF_FIXTURE"), os.Getenv("FLEET5_PEER_PROOF_REPORT")
	if dir == "" || report == "" {
		t.Fatal("invalid proof: isolated fixture and report paths required")
	}
	var metadata struct {
		TenantID, NodeID, Epoch string
		Cycles                  []struct {
			Index                                   int
			Overlap, Final, Certificate, DER_SHA256 string
		}
	}
	raw, err := os.ReadFile(filepath.Join(dir, "fixture.json"))
	if err != nil {
		t.Fatal(err)
	}
	if err = json.Unmarshal(raw, &metadata); err != nil {
		t.Fatal(err)
	}
	if len(metadata.Cycles) != 2 {
		t.Fatal("invalid proof: exactly two generated normal cycles required")
	}
	config := node.Config{TenantID: metadata.TenantID, NodeID: metadata.NodeID, Epoch: metadata.Epoch}
	journalDir, active := filepath.Join(dir, "journal"), filepath.Join(dir, "active-peer.json")
	if err := os.Mkdir(journalDir, 0700); err != nil {
		t.Fatal(err)
	}
	events := []map[string]any{}
	valid, finalRejections, completed := true, 0, 0
	defer func() {
		body, _ := json.MarshalIndent(map[string]any{
			"proofValid": valid, "attemptedNormalCycles": 2, "completedNormalCycles": completed,
			"sameVersionDifferentHashFinalRejections": finalRejections,
			"baselineMismatchConfirmed":               valid && finalRejections == 2,
			"runtimeGOOS":                             goruntime.GOOS, "sameDurableJournal": true,
			"events": events, "operationalAcceptanceAssessed": false,
		}, "", "  ")
		if err := os.WriteFile(report, append(body, '\n'), 0600); err != nil {
			t.Error(err)
		}
	}()
	// Reopen the same real journal for EVERY startup, never an in-memory pin stub.
	start := func(label, policy, cert, expectedDER string) (string, int64, string) {
		bytes, err := os.ReadFile(filepath.Join(dir, policy))
		if err != nil {
			valid = false
			t.Fatal(err)
		}
		if err = os.WriteFile(active, bytes, 0600); err != nil {
			valid = false
			t.Fatal(err)
		}
		var p struct {
			Version int64 `json:"version"`
		}
		if err = json.Unmarshal(bytes, &p); err != nil {
			valid = false
			t.Fatal(err)
		}
		sum := sha256.Sum256(bytes)
		journal, err := node.OpenJournal(journalDir, config)
		if err != nil {
			valid = false
			t.Fatal(err)
		}
		authority, startupErr := NewAuthority(config, filepath.Join(dir, "ca.pem"), active, journal.PinPeerPolicy)
		if startupErr == nil && cert != "" {
			tlsConfig, tlsErr := authority.TLS(filepath.Join(dir, cert), filepath.Join(dir, "node-key.pem"))
			if tlsErr != nil {
				startupErr = tlsErr
			} else {
				pair, pairErr := tlsConfig.GetCertificate(nil)
				if pairErr != nil {
					startupErr = pairErr
				} else {
					der := sha256.Sum256(pair.Certificate[0])
					if hex.EncodeToString(der[:]) != expectedDER {
						startupErr = fmt.Errorf("invalid proof: DER mismatch")
					}
				}
			}
		}
		if err := journal.Close(); err != nil {
			valid = false
			t.Fatal(err)
		}
		floorRaw, err := os.ReadFile(filepath.Join(journalDir, ".peer-policy"))
		if err != nil {
			valid = false
			t.Fatal(err)
		}
		var floor struct {
			Version int64
			Hash    string
		}
		if err := json.Unmarshal(floorRaw, &floor); err != nil {
			valid = false
			t.Fatal(err)
		}
		message := ""
		if startupErr != nil {
			message = startupErr.Error()
		}
		events = append(events, map[string]any{"phase": label, "policyVersion": p.Version,
			"policySHA256": hex.EncodeToString(sum[:]), "accepted": startupErr == nil,
			"error": message, "durableFloorVersion": floor.Version, "durableFloorSHA256": floor.Hash})
		t.Logf("%s policyVersion=%d accepted=%t floor=%d error=%s", label, p.Version, startupErr == nil, floor.Version, message)
		return message, floor.Version, floor.Hash
	}
	message, _, _ := start("initial", "initial-peer.json", "", "")
	if message != "" {
		valid = false
		t.Fatalf("invalid initial fixture/setup: %s", message)
	}
	for _, cycle := range metadata.Cycles {
		message, version, hash := start(fmt.Sprintf("cycle-%d-overlap", cycle.Index), cycle.Overlap, cycle.Certificate, cycle.DER_SHA256)
		if message != "" {
			valid = false
			t.Fatalf("invalid proof: future overlap/TLS must actually start: %s", message)
		}
		message, finalVersion, finalHash := start(fmt.Sprintf("cycle-%d-final", cycle.Index), cycle.Final, cycle.Certificate, cycle.DER_SHA256)
		if message != "" {
			if !strings.Contains(message, "NODE-0041: peer policy rollback rejected") || finalVersion != version || finalHash != hash {
				valid = false
				t.Fatalf("invalid proof: final failed for another cause or floor changed: %s", message)
			}
			finalRejections++
			t.Errorf("BASELINE CONTRACT MISMATCH cycle %d: exact generated final policy must start; same-version/different-bytes is rejected by the real durable peer floor", cycle.Index)
		} else {
			completed++
		}
	}
	// Separate negative: an expired higher-version policy currently pins BEFORE
	// expiry rejection. A startup failure is therefore not proof of unchanged state.
	message, version, hash := start("expired-after-pin-negative", "expired-after-pin.json", "", "")
	if !strings.Contains(message, "NODE-0041: peer policy expired or unbounded") || version != 10 {
		valid = false
		t.Fatalf("invalid expiry-boundary proof: %s floor=%d", message, version)
	}
	negative, err := os.ReadFile(filepath.Join(dir, "expired-after-pin.json"))
	if err != nil {
		valid = false
		t.Fatal(err)
	}
	sum := sha256.Sum256(negative)
	if hash != hex.EncodeToString(sum[:]) {
		valid = false
		t.Fatal("expired policy floor was not the actual persisted bytes")
	}
}
