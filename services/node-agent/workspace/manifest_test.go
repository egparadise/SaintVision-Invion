package workspace

import (
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	contracts "github.com/egparadise/SaintVision-Invion/packages/contracts-go"
	"strings"
	"testing"
)

func example() contracts.WorkspaceSnapshot {
	content := []byte("checkpoint")
	sum := sha256.Sum256(content)
	return contracts.WorkspaceSnapshot{Format: "workspace-snapshot:1", WorkspaceId: "wsp_01J00000000000000000000000", Directories: []string{"src"},
		Files: []contracts.WorkspaceSnapshotFile{{Path: "src/한글🙂.py", Sha256: hex.EncodeToString(sum[:]), SizeBytes: int64(len(content)), DataBase64: base64.StdEncoding.EncodeToString(content)}}}
}
func TestInputHashAndManifest(t *testing.T) {
	s := example()
	raw, _ := json.Marshal(s)
	sum := sha256.Sum256(raw)
	in := &contracts.WorkspaceInput{DataBase64: base64.StdEncoding.EncodeToString(raw), Sha256: hex.EncodeToString(sum[:]), SizeBytes: int64(len(raw))}
	if _, err := Input(in, s.WorkspaceId); err != nil {
		t.Fatal(err)
	}
	in.Sha256 = strings.Repeat("0", 64)
	if _, err := Input(in, s.WorkspaceId); err == nil {
		t.Fatal("tampered input accepted")
	}
}
func TestRejectUnsafePathsAndManifests(t *testing.T) {
	for _, path := range []string{"../escape", "/absolute", "src//file", "src\\file", "src/CON", "src/trailing.", "src/name:stream", "src/a%2fb", "src/\x00", "SRC/file"} {
		t.Run(path, func(t *testing.T) {
			s := example()
			s.Files[0].Path = path
			raw, _ := json.Marshal(s)
			if _, err := Decode(raw, s.WorkspaceId); err == nil {
				t.Fatal("unsafe path accepted")
			}
		})
	}
	t.Run("duplicate", func(t *testing.T) {
		s := example()
		s.Files = append(s.Files, s.Files[0])
		raw, _ := json.Marshal(s)
		if _, err := Decode(raw, s.WorkspaceId); err == nil {
			t.Fatal("duplicate accepted")
		}
	})
	t.Run("digest", func(t *testing.T) {
		s := example()
		s.Files[0].Sha256 = strings.Repeat("a", 64)
		raw, _ := json.Marshal(s)
		if _, err := Decode(raw, s.WorkspaceId); err == nil {
			t.Fatal("wrong hash accepted")
		}
	})
	t.Run("duplicate-key", func(t *testing.T) {
		s := example()
		raw, _ := json.Marshal(s)
		raw = append([]byte(`{"format":"workspace-snapshot:1",`), raw[1:]...)
		if _, err := Decode(raw, s.WorkspaceId); err == nil {
			t.Fatal("duplicate key accepted")
		}
	})
}
