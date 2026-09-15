//go:build linux

package telemetry

import (
	"context"
	"errors"
	"os"
	"strconv"
	"strings"
	"time"
)

func counters(raw string) (uint64, uint64, int64, error) {
	var total, idle uint64
	var cpus int64
	for _, line := range strings.Split(raw, "\n") {
		f := strings.Fields(line)
		if len(f) == 0 {
			continue
		}
		if f[0] == "cpu" {
			if len(f) < 9 {
				return 0, 0, 0, errors.New("incomplete cpu counters")
			}
			for i := 1; i <= 8; i++ {
				n, e := strconv.ParseUint(f[i], 10, 64)
				if e != nil || n > 1<<53 {
					return 0, 0, 0, errors.New("invalid cpu counter")
				}
				total += n
				if i == 4 || i == 5 {
					idle += n
				}
			}
		} else if strings.HasPrefix(f[0], "cpu") {
			if _, err := strconv.Atoi(f[0][3:]); err == nil {
				cpus++
			}
		}
	}
	if total == 0 || cpus < 1 || cpus > 65536 {
		return 0, 0, 0, errors.New("missing cpu counters")
	}
	return total, idle, cpus, nil
}

func memory(raw string) (int64, int64, error) {
	values := map[string]int64{}
	for _, line := range strings.Split(raw, "\n") {
		f := strings.Fields(line)
		if len(f) == 0 || (f[0] != "MemTotal:" && f[0] != "MemAvailable:") {
			continue
		}
		if len(f) != 3 || f[2] != "kB" {
			return 0, 0, errors.New("invalid memory unit")
		}
		n, e := strconv.ParseInt(f[1], 10, 64)
		if e != nil || n < 0 || n > 9007199254740991/1024 {
			return 0, 0, errors.New("invalid memory counter")
		}
		values[f[0]] = n * 1024
	}
	total, tok := values["MemTotal:"]
	available, aok := values["MemAvailable:"]
	if !tok || !aok || total <= 0 || available > total {
		return 0, 0, errors.New("missing memory counters")
	}
	return total, available, nil
}

func Sample(ctx context.Context) (map[string]any, error) {
	first, err := os.ReadFile("/proc/stat")
	if err != nil {
		return nil, err
	}
	t1, i1, c1, err := counters(string(first))
	if err != nil {
		return nil, err
	}
	start := time.Now()
	timer := time.NewTimer(150 * time.Millisecond)
	defer timer.Stop()
	select {
	case <-ctx.Done():
		return nil, ctx.Err()
	case <-timer.C:
	}
	second, err := os.ReadFile("/proc/stat")
	if err != nil {
		return nil, err
	}
	t2, i2, c2, err := counters(string(second))
	if err != nil {
		return nil, err
	}
	elapsed := time.Since(start).Milliseconds()
	if c1 != c2 || t2 <= t1 || i2 < i1 || i2-i1 > t2-t1 || elapsed < 100 || elapsed > 5000 {
		return nil, errors.New("unstable cpu sample")
	}
	mem, err := os.ReadFile("/proc/meminfo")
	if err != nil {
		return nil, err
	}
	total, available, err := memory(string(mem))
	if err != nil {
		return nil, err
	}
	// Round occupied capacity up; guest ticks are already counted in user/nice.
	capacity := c2 * 1000
	delta := t2 - t1
	busy := delta - (i2 - i1)
	used := (busy*uint64(capacity) + delta - 1) / delta
	return map[string]any{"sampleMillis": elapsed, "cpuCapacityMillis": capacity, "cpuBusyMillis": int64(used), "memoryCapacityBytes": total, "memoryAvailableBytes": available, "osType": "linux", "agentVersion": "0.1.0"}, nil
}
