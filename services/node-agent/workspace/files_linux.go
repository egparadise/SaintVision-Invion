//go:build linux

package workspace

import (
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	contracts "github.com/egparadise/SaintVision-Invion/packages/contracts-go"
	"io"
	"io/fs"
	"os"
	"path/filepath"
	"sort"
	"syscall"
)

// Seed runs as trusted PID 1 before any workload, in its empty private tmpfs.
// Paths have been fully validated before any filesystem mutation.
func Seed(root string, s contracts.WorkspaceSnapshot) error {
	raw, err := json.Marshal(s)
	if err != nil {
		return ErrInvalid
	}
	if _, err = Decode(raw, s.WorkspaceId); err != nil {
		return err
	}
	entries, err := os.ReadDir(root)
	if err != nil || len(entries) != 0 {
		return ErrInvalid
	}
	for _, p := range s.Directories {
		if err = os.Mkdir(filepath.Join(root, p), 0700); err != nil {
			return ErrInvalid
		}
	}
	for _, f := range s.Files {
		data, _ := base64.StdEncoding.Strict().DecodeString(f.DataBase64)
		mode := os.FileMode(0600)
		if f.Executable {
			mode = 0700
		}
		out, err := os.OpenFile(filepath.Join(root, f.Path), os.O_WRONLY|os.O_CREATE|os.O_EXCL|syscall.O_NOFOLLOW, mode)
		if err != nil {
			return ErrInvalid
		}
		_, werr := out.Write(data)
		cerr := out.Close()
		if werr != nil || cerr != nil {
			return ErrInvalid
		}
	}
	return nil
}

// Capture is called only after every workload descendant has been killed/reaped.
// It refuses links, devices, FIFOs, hard links and content beyond the fixed budget.
func Capture(root string, id contracts.WorkspaceId) (contracts.WorkspaceSnapshot, error) {
	s := contracts.WorkspaceSnapshot{Format: "workspace-snapshot:1", WorkspaceId: id, Directories: []string{}, Files: []contracts.WorkspaceSnapshotFile{}}
	total := 0
	err := filepath.WalkDir(root, func(path string, entry fs.DirEntry, walkErr error) error {
		if walkErr != nil {
			return ErrInvalid
		}
		if path == root {
			return nil
		}
		name, err := filepath.Rel(root, path)
		if err != nil || !PathOK(name) || len(s.Directories)+len(s.Files) >= 2048 {
			return ErrInvalid
		}
		info, err := entry.Info()
		if err != nil {
			return ErrInvalid
		}
		st, ok := info.Sys().(*syscall.Stat_t)
		if !ok || st.Uid != uint32(os.Geteuid()) || info.Mode()&(os.ModeSetuid|os.ModeSetgid|os.ModeSticky) != 0 {
			return ErrInvalid
		}
		if info.IsDir() {
			s.Directories = append(s.Directories, name)
			return nil
		}
		if !info.Mode().IsRegular() || st.Nlink != 1 || info.Size() > int64(MaxContent-total) {
			return ErrInvalid
		}
		f, err := os.OpenFile(path, os.O_RDONLY|syscall.O_NOFOLLOW|syscall.O_NONBLOCK, 0)
		if err != nil {
			return ErrInvalid
		}
		opened, oerr := f.Stat()
		data, rerr := io.ReadAll(io.LimitReader(f, int64(MaxContent-total)+1))
		f.Close()
		if oerr != nil || rerr != nil || !os.SameFile(info, opened) || len(data) != int(info.Size()) || len(data) > MaxContent-total {
			return ErrInvalid
		}
		total += len(data)
		sum := sha256.Sum256(data)
		s.Files = append(s.Files, contracts.WorkspaceSnapshotFile{Path: name, Executable: info.Mode()&0100 != 0, Sha256: hex.EncodeToString(sum[:]), SizeBytes: int64(len(data)), DataBase64: base64.StdEncoding.EncodeToString(data)})
		return nil
	})
	if err != nil {
		return s, ErrInvalid
	}
	sort.Strings(s.Directories)
	sort.Slice(s.Files, func(i, j int) bool { return s.Files[i].Path < s.Files[j].Path })
	raw, err := json.Marshal(s)
	if err != nil {
		return s, ErrInvalid
	}
	return Decode(raw, id)
}
