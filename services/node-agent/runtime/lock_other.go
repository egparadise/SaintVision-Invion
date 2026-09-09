//go:build !linux

package runtime

import (
	"errors"
	"os"
)

func lockJournal(path string) (*os.File, error) {
	return nil, errors.New("NODE-0011: Linux runtime required")
}
