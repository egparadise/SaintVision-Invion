// Copied only into the actual transport package by the fixed native CI proof.
package transport

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	node "github.com/egparadise/SaintVision-Invion/services/node-agent/runtime"
)

func TestFixedPeerPhaseGuardsPreserveGoFloorDefense(t *testing.T) {
	dir := os.Getenv("FLEET5_FIXED_NATIVE_FIXTURE")
	if dir == "" {
		t.Fatal("isolated native fixture required")
	}
	var config node.Config
	raw, err := os.ReadFile(filepath.Join(dir, "config.json"))
	if err != nil {
		t.Fatal(err)
	}
	if err = json.Unmarshal(raw, &config); err != nil {
		t.Fatal(err)
	}
	state := filepath.Join(t.TempDir(), "journal")
	journal, err := node.OpenJournal(state, config)
	if err != nil {
		t.Fatal(err)
	}
	defer journal.Close()
	policy := filepath.Join(filepath.Dir(state), "peer-policy.json")
	apply := func(name string) error {
		body, err := os.ReadFile(filepath.Join(dir, name))
		if err != nil {
			t.Fatal(err)
		}
		if err = os.WriteFile(policy, body, 0600); err != nil {
			t.Fatal(err)
		}
		_, err = NewAuthority(config, filepath.Join(dir, "ca.pem"), policy, journal.PinPeerPolicy)
		return err
	}
	if err = apply("overlap.json"); err != nil {
		t.Fatalf("valid overlap setup must succeed: %v", err)
	}
	before, err := os.ReadFile(filepath.Join(state, ".peer-policy"))
	if err != nil {
		t.Fatal(err)
	}
	if err = apply("same-version-final.json"); err == nil || !strings.Contains(err.Error(), "NODE-0041: peer policy rollback rejected") {
		t.Fatalf("same-version changed hash admitted/wrong error: %v", err)
	}
	after, err := os.ReadFile(filepath.Join(state, ".peer-policy"))
	if err != nil || string(before) != string(after) {
		t.Fatal("rejected same-version policy changed durable floor")
	}
	if err = apply("expired.json"); err == nil || !strings.Contains(err.Error(), "NODE-0041: peer policy expired or unbounded") {
		t.Fatalf("expiry boundary wrong: %v", err)
	}
	var floor struct {
		Version int64
		Hash    string
	}
	after, err = os.ReadFile(filepath.Join(state, ".peer-policy"))
	if err != nil {
		t.Fatal(err)
	}
	if err = json.Unmarshal(after, &floor); err != nil {
		t.Fatal(err)
	}
	expired, err := os.ReadFile(filepath.Join(dir, "expired.json"))
	if err != nil {
		t.Fatal(err)
	}
	hash := sha256.Sum256(expired)
	if floor.Version != 12 || floor.Hash != hex.EncodeToString(hash[:]) {
		t.Fatal("expired startup did not preserve its real first-pin boundary")
	}
}
