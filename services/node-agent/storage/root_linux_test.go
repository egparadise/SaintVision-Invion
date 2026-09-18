//go:build linux

package storage

import (
	"context"
	"os"
	"path/filepath"
	"syscall"
	"testing"
)

func TestRootAndFileBoundary(t *testing.T) {
	for _, fault := range []string{"valid", "symlink", "hardlink", "parent-link", "root-replaced", "oversized", "fifo"} {
		t.Run(fault, func(t *testing.T) {
			base := t.TempDir()
			path := filepath.Join(base, "root")
			os.Mkdir(path, 0700)
			file := filepath.Join(path, "file")
			os.WriteFile(file, []byte("abc"), 0600)
			root, err := openRoot(path)
			if err != nil {
				t.Fatal(err)
			}
			defer root.close()
			name := "file"
			switch fault {
			case "symlink":
				os.Remove(file)
				os.Symlink(filepath.Join(base, "outside"), file)
			case "hardlink":
				os.Link(file, filepath.Join(base, "alias"))
			case "parent-link":
				os.Symlink(path, filepath.Join(path, "link"))
				name = "link/file"
			case "root-replaced":
				os.Rename(path, path+"-old")
				os.Mkdir(path, 0700)
				os.WriteFile(file, []byte("abc"), 0600)
			case "oversized":
				f, _ := os.OpenFile(file, os.O_WRONLY, 0600)
				f.Truncate(MaxBytes + 1)
				f.Close()
			case "fifo":
				os.Remove(file)
				syscall.Mkfifo(file, 0600)
			}
			sum, n, err := root.hash(context.Background(), name)
			if fault == "valid" {
				if err != nil || n != 3 || sum != "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad" {
					t.Fatal("valid read failed", err)
				}
			} else if err == nil {
				t.Fatal("unsafe read accepted")
			}
		})
	}
}
func TestRootAncestorSymlinkAndFilesystemRootRejected(t *testing.T) {
	base := t.TempDir()
	os.Mkdir(filepath.Join(base, "actual"), 0700)
	os.Mkdir(filepath.Join(base, "actual", "nested"), 0700)
	os.Symlink(filepath.Join(base, "actual"), filepath.Join(base, "link"))
	for _, path := range []string{"/", filepath.Join(base, "link", "nested")} {
		if root, err := openRoot(path); err == nil {
			root.close()
			t.Fatal("unsafe root accepted")
		}
	}
}
