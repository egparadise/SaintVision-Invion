//go:build linux

package workspace

import (
	"os"
	"path/filepath"
	"strings"
	"syscall"
	"testing"
)

func TestSeedEditCapture(t *testing.T) {
	root := t.TempDir()
	s := example()
	if err := Seed(root, s); err != nil {
		t.Fatal(err)
	}
	if err := Seed(root, s); err == nil {
		t.Fatal("nonempty overwrite")
	}
	os.WriteFile(filepath.Join(root, s.Files[0].Path), []byte("edited"), 0600)
	got, err := Capture(root, s.WorkspaceId)
	if err != nil || len(got.Files) != 1 || got.Files[0].SizeBytes != 6 {
		t.Fatalf("capture: %v", err)
	}
}
func TestCaptureRejectsUnsafeFiles(t *testing.T) {
	for _, attack := range []string{"symlink", "hardlink", "fifo", "oversized"} {
		t.Run(attack, func(t *testing.T) {
			root := t.TempDir()
			path := filepath.Join(root, "bad")
			outside := filepath.Join(t.TempDir(), "outside")
			os.WriteFile(outside, []byte("private"), 0600)
			switch attack {
			case "symlink":
				os.Symlink(outside, path)
			case "hardlink":
				os.Link(outside, path)
			case "fifo":
				syscall.Mkfifo(path, 0600)
			case "oversized":
				os.WriteFile(path, []byte(strings.Repeat("x", MaxContent+1)), 0600)
			}
			if _, err := Capture(root, example().WorkspaceId); err == nil {
				t.Fatal("unsafe capture")
			}
		})
	}
}
