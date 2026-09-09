//go:build !linux

package transfer

import (
	"context"
	"errors"
)

type Source struct{}
type Request struct {
	SHA256 string `json:"sha256"`
	Size   int64  `json:"sizeBytes"`
	Offset int64  `json:"offset"`
	Nonce  string `json:"nonce"`
}

func Open(string) (*Source, error) { return nil, errors.New("object provider requires Linux") }
func (*Source) Close() error       { return nil }
func (*Source) Read(context.Context, Request) (map[string]any, error) {
	return nil, errors.New("object provider requires Linux")
}
