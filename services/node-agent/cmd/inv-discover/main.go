package main

import (
	"context"
	"flag"
	"fmt"
	"github.com/egparadise/SaintVision-Invion/services/node-agent/discovery"
	"github.com/egparadise/SaintVision-Invion/services/node-agent/telemetry"
	"os"
	"os/signal"
	"runtime"
	"strings"
	"syscall"
	"time"
)

func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, "Node announcement unavailable")
		os.Exit(1)
	}
}
func run() error {
	var endpoint, tenant, instance, caFile string
	var once bool
	flag.StringVar(&endpoint, "endpoint", "", "explicit HTTPS announcement endpoint")
	flag.StringVar(&tenant, "tenant", "", "target tenant (must match the bearer credential)")
	flag.StringVar(&instance, "instance", "", "operator-stable installation identifier")
	flag.StringVar(&caFile, "ca", "", "explicit discovery server CA PEM")
	flag.BoolVar(&once, "once", false, "announce once")
	flag.Parse()
	bearer := strings.TrimSpace(os.Getenv("INV_DISCOVERY_BEARER_TOKEN"))
	if bearer == "" || strings.ContainsAny(bearer, "\r\n") {
		return fmt.Errorf("tenant discovery credential unavailable")
	}
	ca, err := os.ReadFile(caFile)
	if err != nil || len(ca) > 65536 {
		return fmt.Errorf("CA unavailable")
	}
	hostname, err := os.Hostname()
	if err != nil {
		return err
	}
	a := discovery.Announcement{InstanceID: instance, Hostname: hostname, OSType: runtime.GOOS, OSVersion: "unavailable", AgentVersion: "0.1.0", CPUCores: runtime.NumCPU(), Labels: map[string]string{"memoryMeasurement": "unavailable", "gpuMeasurement": "unavailable"}}
	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer cancel()
	if sample, err := telemetry.Sample(ctx); err == nil {
		a.RAMBytes = sample["memoryCapacityBytes"].(int64)
		a.Labels["memoryMeasurement"] = "self-reported"
	}
	if runtime.GOOS == "linux" {
		if raw, err := os.ReadFile("/proc/sys/kernel/osrelease"); err == nil && len(strings.TrimSpace(string(raw))) <= 64 {
			a.OSVersion = strings.TrimSpace(string(raw))
		}
	}
	for {
		err = discovery.Send(ctx, endpoint, tenant, "Bearer "+bearer, ca, a)
		if once {
			return err
		}
		timer := time.NewTimer(30 * time.Second)
		select {
		case <-ctx.Done():
			timer.Stop()
			return nil
		case <-timer.C:
		}
	}
}
