//go:build linux

package main

import (
	"bytes"
	"sync"
	"testing"
)

func TestOutputFloodIsBoundedAndDrainedConcurrently(t *testing.T) {
	b := &outputBuffer{}
	var wg sync.WaitGroup
	for i := 0; i < 8; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			p := bytes.Repeat([]byte("x"), 20000)
			n, err := b.Write(p)
			if err != nil || n != len(p) {
				t.Error("output was not drained")
			}
		}()
	}
	wg.Wait()
	if len(b.data) != 65536 || !b.truncated {
		t.Fatal("output cap not enforced")
	}
}
