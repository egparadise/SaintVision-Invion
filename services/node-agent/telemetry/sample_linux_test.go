//go:build linux

package telemetry

import (
	"context"
	"testing"
)

func TestCountersDoNotDoubleCountGuest(t *testing.T) {
	total, idle, cpus, err := counters("cpu 100 10 20 400 5 3 2 1 70 10\ncpu0 0\ncpu1 0\n")
	if err != nil || total != 541 || idle != 405 || cpus != 2 {
		t.Fatalf("invalid counters: %d %d %d %v", total, idle, cpus, err)
	}
}
func TestMissingMemoryNeverBecomesIdle(t *testing.T) {
	for _, raw := range []string{"MemTotal: 42 kB", "MemTotal: 42 kB\nMemAvailable: 43 kB", "MemTotal: 42 MB\nMemAvailable: 1 MB"} {
		if _, _, err := memory(raw); err == nil {
			t.Fatal("invalid memory accepted")
		}
	}
}
func TestRealHostSampleAndCancellation(t *testing.T) {
	value, err := Sample(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if value["cpuBusyMillis"].(int64) > value["cpuCapacityMillis"].(int64) || value["memoryAvailableBytes"].(int64) > value["memoryCapacityBytes"].(int64) {
		t.Fatal("invalid measured capacity")
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if _, err = Sample(ctx); err == nil {
		t.Fatal("canceled sample completed")
	}
}
