// Synthetic CI probe only. It is copied into a FROM scratch image with no host mounts.
package main

import (
	"fmt"
	"net"
	"os"
	"os/exec"
	"strings"
	"time"
)

func fail(reason string) { fmt.Fprintln(os.Stderr, reason); os.Exit(41) }
func main() {
	if len(os.Args) > 1 && os.Args[1] == "workspace" {
		data, err := os.ReadFile("/workspace/src/main.py")
		if err != nil || string(data) != "print('checkpoint')\n" {
			fail("restored input")
		}
		if os.Getenv("INV_WORKSPACE_INPUT") != "" {
			fail("private input environment")
		}
		if err = os.WriteFile("/workspace/src/main.py", []byte("print('resumed')\n"), 0600); err != nil {
			fail("resumed write")
		}
		if len(os.Args) > 2 && os.Args[2] == "symlink" {
			os.Symlink("/etc/passwd", "/workspace/escape")
			return
		}
		if len(os.Args) > 2 && os.Args[2] == "overflow" {
			os.WriteFile("/workspace/overflow", []byte(strings.Repeat("x", 33000)), 0600)
			return
		}
		os.Mkdir("/tmp/empty-template", 0700)
		commands := [][]string{{"-c", "init.defaultBranch=main", "init", "--template=/tmp/empty-template"}, {"add", "src/main.py"},
			{"-c", "user.name=Synthetic Test", "-c", "user.email=synthetic@example.invalid", "-c", "commit.gpgsign=false", "commit", "-m", "resumed step"}, {"rev-parse", "HEAD"}}
		for _, args := range commands {
			cmd := exec.Command("/usr/bin/git", args...)
			cmd.Dir = "/workspace"
			cmd.Env = []string{"PATH=/usr/bin:/bin", "HOME=/workspace", "GIT_CONFIG_NOSYSTEM=1", "GIT_CONFIG_GLOBAL=/dev/null"}
			out, err := cmd.CombinedOutput()
			if err != nil {
				fail("local Git failed")
			}
			if args[0] == "rev-parse" {
				fmt.Print(string(out))
			}
		}
		return
	}
	if len(os.Args) > 1 && os.Args[1] == "sleep" {
		time.Sleep(60 * time.Second)
		return
	}
	if len(os.Args) > 1 && os.Args[1] == "fail" {
		os.Exit(7)
	}
	if len(os.Args) > 1 && os.Args[1] == "output" {
		fmt.Fprintln(os.Stdout, "actual-node-output")
		fmt.Fprintln(os.Stderr, "actual-node-stderr")
		return
	}
	if len(os.Args) > 1 && os.Args[1] == "overflow" {
		fmt.Fprint(os.Stdout, strings.Repeat("x", 70000))
		return
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
