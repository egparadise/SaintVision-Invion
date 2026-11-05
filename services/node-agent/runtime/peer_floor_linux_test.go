//go:build linux

package runtime

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestActualPeerFloorExecutableDigestUsesDescriptorBytes(t *testing.T) {
	value, err := ServingExecutableSHA256(os.Getpid(), uint32(os.Geteuid()))
	if err != nil {
		t.Fatal(err)
	}
	raw, err := os.ReadFile("/proc/self/exe")
	if err != nil {
		t.Fatal(err)
	}
	digest := sha256.Sum256(raw)
	if value != hex.EncodeToString(digest[:]) {
		t.Fatal("executable digest is not actual descriptor bytes")
	}
	cmd, err := os.ReadFile("/proc/self/cmdline")
	if err != nil {
		t.Fatal(err)
	}
	argv := sha256.Sum256(cmd)
	if value == hex.EncodeToString(argv[:]) {
		t.Fatal("raw command line was mislabeled as executable bytes")
	}
	if _, err := ServingExecutableSHA256(os.Getpid(), uint32(os.Geteuid())+1); err == nil {
		t.Fatal("foreign process UID admitted")
	}
	if _, err := ServingExecutableSHA256(0, uint32(os.Geteuid())); err == nil {
		t.Fatal("missing process admitted")
	}
}

func peerFloorFixture(t *testing.T) (string, string, Config, *Journal) {
	t.Helper()
	parent := t.TempDir()
	if err := os.Chmod(parent, 0700); err != nil {
		t.Fatal(err)
	}
	state := filepath.Join(parent, "journal")
	c := Config{TenantID: "00000000-0000-4000-8000-000000000001", NodeID: "nod_00000000000000000000000000", Epoch: "00000000-0000-4000-8000-000000000002"}
	j, err := OpenJournal(state, c)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { j.Close() })
	policy := []byte(fmt.Sprintf(`{"version":7,"tenantId":%q,"nodeId":%q,"recoveryEpoch":%q,"expiresAt":%q,"clientFingerprints":[%q]}`, c.TenantID, c.NodeID, c.Epoch, time.Now().Add(time.Hour).UTC().Format(time.RFC3339), "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"))
	path := filepath.Join(parent, "peer-policy.json")
	if err := os.WriteFile(path, policy, 0600); err != nil {
		t.Fatal(err)
	}
	h := sha256.Sum256(policy)
	if err := j.PinPeerPolicy(7, hex.EncodeToString(h[:])); err != nil {
		t.Fatal(err)
	}
	return state, path, c, j
}

func TestActualPeerFloorObservationRetainsServingJournalLock(t *testing.T) {
	state, policy, c, _ := peerFloorFixture(t)
	before, err := os.ReadFile(filepath.Join(state, ".peer-policy"))
	if err != nil {
		t.Fatal(err)
	}
	observed, err := ReadPeerPolicyFloor(state, policy, c)
	if err != nil || observed.Version != 7 {
		t.Fatalf("actual read while serving lock held: %v %+v", err, observed)
	}
	if another, err := OpenJournal(state, c); err == nil {
		another.Close()
		t.Fatal("observer must not steal/release serving lock")
	}
	after, err := os.ReadFile(filepath.Join(state, ".peer-policy"))
	if err != nil || string(before) != string(after) {
		t.Fatal("observer mutated floor")
	}
}

func TestActualPeerFloorObservationStrictExistingState(t *testing.T) {
	for _, fault := range []string{"missing", "symlink", "hardlink", "mode", "bool", "float", "duplicate", "unknown", "hash-mismatch", "identity", "policy-changed", "directory-mode", "relative"} {
		t.Run(fault, func(t *testing.T) {
			state, policy, c, _ := peerFloorFixture(t)
			floor := filepath.Join(state, ".peer-policy")
			switch fault {
			case "missing":
				os.Remove(floor)
			case "symlink":
				original := floor + "-original"
				os.Rename(floor, original)
				if err := os.Symlink(original, floor); err != nil {
					t.Fatal(err)
				}
			case "hardlink":
				if err := os.Link(floor, floor+"-alias"); err != nil {
					t.Fatal(err)
				}
			case "mode":
				os.Chmod(floor, 0644)
			case "bool":
				os.WriteFile(floor, []byte(`{"Version":true,"Hash":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}`), 0600)
			case "float":
				os.WriteFile(floor, []byte(`{"Version":7.0,"Hash":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}`), 0600)
			case "duplicate":
				os.WriteFile(floor, []byte(`{"Version":7,"Version":7,"Hash":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}`), 0600)
			case "unknown":
				os.WriteFile(floor, []byte(`{"Version":7,"Hash":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","other":0}`), 0600)
			case "hash-mismatch":
				os.WriteFile(floor, []byte(`{"Version":7,"Hash":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}`), 0600)
			case "identity":
				c.Epoch = "00000000-0000-4000-8000-000000000003"
			case "policy-changed":
				os.WriteFile(policy, []byte(`{}`), 0600)
			case "directory-mode":
				os.Chmod(state, 0755)
			case "relative":
				state = "relative"
			}
			if _, err := ReadPeerPolicyFloor(state, policy, c); err == nil {
				t.Fatal("unsafe actual floor observation accepted")
			}
		})
	}
}

func TestActualPeerFloorObservationChecksJournalUID(t *testing.T) {
	state, _, _, _ := peerFloorFixture(t)
	directory, info, err := existingDirectory(state)
	if err != nil {
		t.Fatal(err)
	}
	defer directory.Close()
	if _, err := observedEntry(directory, ".peer-policy", info.Uid+1); err == nil {
		t.Fatal("file owner different from journal owner accepted")
	}
}
