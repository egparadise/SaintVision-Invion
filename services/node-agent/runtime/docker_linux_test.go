//go:build linux

package runtime

import (
	"context"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"os"
	"testing"
)

// Explicit opt-in; uses a local prebuilt /probe + supervisor image. Each
// synthetic claim has a random command/epoch; no production credentials or DB.
func TestDockerLiveCompatibility(t *testing.T) {
	if os.Getenv("INV_RUN_DOCKER_COMPAT") != "1" {
		t.Skip("real Docker opt-in required")
	}
	image := os.Getenv("INV_NODE_IMAGE")
	if len(image) != 71 {
		t.Fatal("pinned probe image required")
	}
	for _, mode := range []string{"isolation", "output", "fail", "sleep"} {
		t.Run(mode, func(t *testing.T) {
			c, p, key := fixture(t)
			c.Image = image
			p.Launch.ImageDigest = image
			p.Launch.Argv = []string{"/probe"}
			if mode != "isolation" {
				p.Launch.Argv = append(p.Launch.Argv, mode)
			}
			if mode == "sleep" {
				p.Launch.TimeoutSeconds = 1
			}
			engine, err := NewDocker("/var/run/docker.sock")
			if err != nil {
				t.Fatal(err)
			}
			runner := New(c, journalFor(t, c), engine)
			t.Cleanup(func() {
				if _, err := runner.Recover(context.Background()); err != nil {
					t.Error("test cleanup remains uncertain", err)
				}
			})
			permit := signed(t, p, key)
			result, err := runner.Execute(context.Background(), permit)
			if err != nil {
				t.Fatal(err)
			}
			r := result.Receipt
			if result.CleanupPending || r == nil || !r.ProcessStarted || !r.Stopped {
				t.Fatalf("unverified execution: %+v", result)
			}
			if ((mode == "isolation" || mode == "output") && r.ExitCode != 0) || (mode == "fail" && r.ExitCode != 7) || (mode == "sleep" && r.ExitCode == 0) {
				t.Fatalf("exit=%d", r.ExitCode)
			}
			outputHash := "not-collected-for-failed-execution"
			if r.ExitCode == 0 {
				if r.Output == nil {
					t.Fatal("successful output missing")
				}
				data, err := base64.StdEncoding.DecodeString(r.Output.Data)
				if err != nil {
					t.Fatal(err)
				}
				sum := sha256.Sum256(data)
				if int64(len(data)) != r.Output.SizeBytes || hex.EncodeToString(sum[:]) != r.Output.Sha256 {
					t.Fatal("output integrity differs")
				}
				outputHash = r.Output.Sha256
				if mode == "output" {
					var artifact struct{ Stdout, Stderr string }
					if json.Unmarshal(data, &artifact) != nil {
						t.Fatal("invalid artifact")
					}
					stdout, _ := base64.StdEncoding.DecodeString(artifact.Stdout)
					stderr, _ := base64.StdEncoding.DecodeString(artifact.Stderr)
					if string(stdout) != "actual-node-output\n" || string(stderr) != "actual-node-stderr\n" {
						t.Fatal("actual process output differs")
					}
				}
			} else if r.Output != nil {
				t.Fatal("failed execution must not attest successful output")
			}
			again, err := runner.Execute(context.Background(), permit)
			if err != nil || !again.Duplicate || again.Receipt.ReceiptId != r.ReceiptId {
				t.Fatal("durable replay differs", err)
			}
			// Runner must remove only the verified stopped execution container.
			record := Record{Claim: p.Claim, Name: containerName(p.Claim)}
			if _, err = engine.Inspect(context.Background(), record.Name, record); !errors.Is(err, ErrAbsent) {
				t.Fatal("execution container not removed", err)
			}
			t.Logf("api=%s mode=%s exit=%d outputSHA256=%s duplicate=true cleanup=true", engine.version, mode, r.ExitCode, outputHash)
		})
	}
}
