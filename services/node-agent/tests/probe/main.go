// Synthetic CI probe only. It is copied into a FROM scratch image with no host mounts.
package main

import (
	"fmt"
	"net"
	"os"
	"strings"
	"time"
)

func fail(reason string) { fmt.Fprintln(os.Stderr, reason); os.Exit(41) }
func main() {
	if len(os.Args) > 1 && os.Args[1] == "sleep" {
		time.Sleep(60 * time.Second)
		return
	}
	if len(os.Args) > 1 && os.Args[1] == "fail" {
		os.Exit(7)
	}
	if os.Geteuid() != 65532 {
		fail("uid")
	}
	status, err := os.ReadFile("/proc/self/status")
	if err != nil {
		fail("proc")
	}
	for _, line := range strings.Split(string(status), "\n") {
		if strings.HasPrefix(line, "CapEff:") && strings.TrimSpace(strings.TrimPrefix(line, "CapEff:")) != "0000000000000000" {
			fail("capabilities")
		}
		if strings.HasPrefix(line, "NoNewPrivs:") && strings.TrimSpace(strings.TrimPrefix(line, "NoNewPrivs:")) != "1" {
			fail("privileges")
		}
	}
	interfaces, err := net.Interfaces()
	if err != nil {
		fail("network")
	}
	for _, iface := range interfaces {
		if iface.Name != "lo" {
			fail("network namespace")
		}
	}
	if _, err := os.Stat("/var/run/docker.sock"); !os.IsNotExist(err) {
		fail("host socket")
	}
	if err := os.WriteFile("/escape", []byte("blocked"), 0600); err == nil {
		fail("root write")
	}
	if err := os.WriteFile("/workspace/synthetic", []byte("allowed"), 0600); err != nil {
		fail("workspace")
	}
	for file, want := range map[string]string{"/sys/fs/cgroup/pids.max": "64", "/sys/fs/cgroup/memory.max": "67108864"} {
		data, err := os.ReadFile(file)
		if err != nil || strings.TrimSpace(string(data)) != want {
			fail("cgroup")
		}
	}
	cpu, err := os.ReadFile("/sys/fs/cgroup/cpu.max")
	if err != nil || strings.HasPrefix(string(cpu), "max") {
		fail("cpu quota")
	}
}
