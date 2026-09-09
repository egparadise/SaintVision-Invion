//go:build linux

package runtime

import (
	"errors"
	"os"
	"syscall"
)

func lockJournal(path string) (*os.File, error) {
	fd, err := syscall.Open(path, syscall.O_CREAT|syscall.O_RDWR|syscall.O_NOFOLLOW, 0600)
	if err != nil {
		return nil, errors.New("NODE-0011: journal lock unavailable")
	}
	file := os.NewFile(uintptr(fd), path)
	if err = syscall.Flock(fd, syscall.LOCK_EX|syscall.LOCK_NB); err != nil {
		_ = file.Close()
		return nil, errors.New("NODE-0011: another Node worker owns journal")
	}
	return file, nil
}
