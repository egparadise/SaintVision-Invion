//go:build linux

package storage

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"io"
	"os"
	"path/filepath"
	"strings"
	"syscall"
)

type readRoot struct {
	file     *os.File
	path     string
	identity syscall.Stat_t
}

// Walk every ancestor, not just the final root component, without symlinks.
func directory(path string) (*os.File, error) {
	if !filepath.IsAbs(path) || filepath.Clean(path) != path {
		return nil, rejected
	}
	fd, err := syscall.Open("/", syscall.O_RDONLY|syscall.O_DIRECTORY|syscall.O_CLOEXEC, 0)
	if err != nil {
		return nil, err
	}
	for _, part := range strings.Split(strings.TrimPrefix(path, "/"), "/") {
		if part == "" {
			continue
		}
		next, e := syscall.Openat(fd, part, syscall.O_RDONLY|syscall.O_DIRECTORY|syscall.O_NOFOLLOW|syscall.O_CLOEXEC, 0)
		syscall.Close(fd)
		if e != nil {
			return nil, e
		}
		fd = next
	}
	return os.NewFile(uintptr(fd), "storage-root"), nil
}
func openRoot(path string) (*readRoot, error) {
	if path == "/" {
		return nil, rejected
	}
	f, err := directory(path)
	if err != nil {
		return nil, err
	}
	var stat syscall.Stat_t
	if err = syscall.Fstat(int(f.Fd()), &stat); err != nil {
		f.Close()
		return nil, err
	}
	return &readRoot{f, path, stat}, nil
}
func (r *readRoot) close() error    { return r.file.Close() }
func same(a, b syscall.Stat_t) bool { return a.Dev == b.Dev && a.Ino == b.Ino }
func (r *readRoot) current() error {
	f, err := directory(r.path)
	if err != nil {
		return err
	}
	defer f.Close()
	var stat syscall.Stat_t
	if syscall.Fstat(int(f.Fd()), &stat) != nil || !same(stat, r.identity) {
		return rejected
	}
	return nil
}
func (r *readRoot) open(path string) (*os.File, error) {
	if !validPath(path) || r.current() != nil {
		return nil, rejected
	}
	fd, err := syscall.Dup(int(r.file.Fd()))
	if err != nil {
		return nil, err
	}
	syscall.CloseOnExec(fd)
	parts := strings.Split(path, "/")
	for i, part := range parts {
		flags := syscall.O_RDONLY | syscall.O_NOFOLLOW | syscall.O_CLOEXEC | syscall.O_NONBLOCK
		if i < len(parts)-1 {
			flags |= syscall.O_DIRECTORY
		}
		next, e := syscall.Openat(fd, part, flags, 0)
		syscall.Close(fd)
		if e != nil {
			return nil, e
		}
		fd = next
		var st syscall.Stat_t
		if syscall.Fstat(fd, &st) != nil || st.Dev != r.identity.Dev {
			syscall.Close(fd)
			return nil, rejected
		}
	}
	return os.NewFile(uintptr(fd), "storage-sample"), nil
}
func (r *readRoot) hash(ctx context.Context, path string) (string, int64, error) {
	f, err := r.open(path)
	if err != nil {
		return "", 0, err
	}
	defer f.Close()
	var initial syscall.Stat_t
	if syscall.Fstat(int(f.Fd()), &initial) != nil || initial.Mode&syscall.S_IFMT != syscall.S_IFREG || initial.Nlink != 1 || initial.Size < 0 || initial.Size > MaxBytes {
		return "", 0, rejected
	}
	var first string
	for attempt := 0; attempt < 2; attempt++ {
		if _, err = f.Seek(0, io.SeekStart); err != nil {
			return "", 0, err
		}
		digest := sha256.New()
		var total int64
		buf := make([]byte, 65536)
		remaining := initial.Size + 1
		for remaining > 0 {
			if ctx.Err() != nil {
				return "", 0, ctx.Err()
			}
			want := int64(len(buf))
			if remaining < want {
				want = remaining
			}
			n, e := f.Read(buf[:want])
			digest.Write(buf[:n])
			total += int64(n)
			remaining -= int64(n)
			if e == io.EOF {
				break
			}
			if e != nil {
				return "", 0, e
			}
			if n == 0 {
				return "", 0, rejected
			}
		}
		sum := hex.EncodeToString(digest.Sum(nil))
		if total != initial.Size || (attempt == 1 && sum != first) {
			return "", 0, rejected
		}
		first = sum
	}
	var final syscall.Stat_t
	if syscall.Fstat(int(f.Fd()), &final) != nil || !same(initial, final) || initial.Size != final.Size || initial.Mtim != final.Mtim || initial.Ctim != final.Ctim || final.Nlink != 1 {
		return "", 0, rejected
	}
	current, err := r.open(path)
	if err != nil {
		return "", 0, err
	}
	defer current.Close()
	var named syscall.Stat_t
	if syscall.Fstat(int(current.Fd()), &named) != nil || !same(initial, named) || named.Nlink != 1 || named.Size != final.Size || named.Mtim != final.Mtim || named.Ctim != final.Ctim || r.current() != nil {
		return "", 0, rejected
	}
	return first, initial.Size, nil
}
