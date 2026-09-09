//go:build !linux

package telemetry

import (
	"context"
	"errors"
)

func Sample(context.Context) (map[string]any, error) {
	return nil, errors.New("OS resource sampler is unavailable")
}
