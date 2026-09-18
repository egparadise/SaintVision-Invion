//go:build linux

package transfer

import (
	"context"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"errors"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"syscall"
)

const ChunkBytes = 256 * 1024

var digestPattern = regexp.MustCompile(`^[0-9a-f]{64}$`)

type Source struct{ root *os.File }
type Request struct {
	SHA256 string `json:"sha256"`
	Size   int64  `json:"sizeBytes"`
	Offset int64  `json:"offset"`
	Nonce  string `json:"nonce"`
}

func Open(root string) (*Source, error) {
	if !filepath.IsAbs(root) {
		return nil, errors.New("explicit object directory required")
	}
	fd, err := syscall.Open(root, syscall.O_RDONLY|syscall.O_DIRECTORY|syscall.O_NOFOLLOW, 0)
	if err != nil {
		return nil, err
	}
	file := os.NewFile(uintptr(fd), "objects")
	var info syscall.Stat_t
	if err = syscall.Fstat(fd, &info); err != nil || info.Uid != uint32(os.Geteuid()) || info.Mode&0077 != 0 {
		file.Close()
		return nil, errors.New("private object directory required")
	}
	return &Source{file}, nil
}
func (s *Source) Close() error { return s.root.Close() }

type checkedReader struct {
	ctx context.Context
	r   io.Reader
}

func (r checkedReader) Read(p []byte) (int, error) {
	select {
	case <-r.ctx.Done():
		return 0, r.ctx.Err()
	default:
		return r.r.Read(p)
	}
}
func (s *Source) Read(ctx context.Context, in Request) (map[string]any, error) {
	if s == nil || !digestPattern.MatchString(in.SHA256) || in.Size < 0 || in.Size > 64*1024*1024 || in.Offset < 0 || in.Offset > in.Size || in.Offset%ChunkBytes != 0 {
		return nil, errors.New("invalid bounded object request")
	}
	fd, err := syscall.Openat(int(s.root.Fd()), in.SHA256, syscall.O_RDONLY|syscall.O_NOFOLLOW|syscall.O_NONBLOCK, 0)
	if err != nil {
		return nil, err
	}
	file := os.NewFile(uintptr(fd), "object")
	defer file.Close()
	var info syscall.Stat_t
	if err = syscall.Fstat(fd, &info); err != nil || info.Mode&syscall.S_IFMT != syscall.S_IFREG || info.Nlink != 1 || info.Uid != uint32(os.Geteuid()) || info.Mode&0222 != 0 || info.Size != in.Size {
		return nil, errors.New("invalid object handle")
	}
	hash := sha256.New()
	n, err := io.Copy(hash, checkedReader{ctx, io.LimitReader(file, in.Size+1)})
	if err != nil || n != in.Size || hex.EncodeToString(hash.Sum(nil)) != in.SHA256 {
		return nil, errors.New("object checksum differs")
	}
	if _, err = file.Seek(in.Offset, io.SeekStart); err != nil {
		return nil, err
	}
	data, err := io.ReadAll(checkedReader{ctx, io.LimitReader(file, ChunkBytes)})
	if err != nil {
		return nil, err
	}
	expected := in.Size - in.Offset
	if expected > ChunkBytes {
		expected = ChunkBytes
	}
	if int64(len(data)) != expected {
		return nil, errors.New("object changed")
	}
	sum := sha256.Sum256(data)
	return map[string]any{"sha256": in.SHA256, "sizeBytes": in.Size, "offset": in.Offset, "nonce": in.Nonce, "dataBase64": base64.StdEncoding.EncodeToString(data), "chunkSha256": hex.EncodeToString(sum[:])}, nil
}
