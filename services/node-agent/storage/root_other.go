//go:build !linux

package storage

import "context"

type readRoot struct{}

func openRoot(string) (*readRoot, error)                              { return nil, rejected }
func (*readRoot) close() error                                        { return nil }
func (*readRoot) current() error                                      { return rejected }
func (*readRoot) hash(context.Context, string) (string, int64, error) { return "", 0, rejected }
