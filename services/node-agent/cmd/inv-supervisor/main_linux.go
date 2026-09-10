//go:build linux

// The trusted PID 1 watchdog is baked into each approved image. Its timer survives
// Node-agent death; exiting PID 1 terminates all descendants in this PID namespace.
package main

import (
	"encoding/json"
	"flag"
	contracts "github.com/egparadise/SaintVision-Invion/packages/contracts-go"
	"github.com/egparadise/SaintVision-Invion/services/node-agent/workspace"
	"os"
	"os/exec"
	"os/signal"
	"syscall"
	"time"
)

func main() { os.Exit(run()) }
func run() int {
	var expiry string
	var seconds int
	flag.StringVar(&expiry, "not-after", "", "signed upper deadline")
	flag.IntVar(&seconds, "timeout", 0, "maximum workload duration")
	flag.Parse()
	if os.Getpid() != 1 || os.Geteuid() != 65532 || seconds < 1 || seconds > 30 || len(flag.Args()) == 0 {
		return 125
	}
	// A workload with the same UID must not ptrace/alter its trusted parent.
	if _, _, err := syscall.Syscall6(syscall.SYS_PRCTL, 4, 0, 0, 0, 0, 0); err != 0 {
		return 125
	}
	now := time.Now()
	deadline, err := time.Parse(time.RFC3339Nano, expiry)
	if err != nil {
		return 125
	}
	remaining := deadline.Sub(now) - 5*time.Second
	if remaining <= 0 {
		return 124
	}
	if limit := time.Duration(seconds) * time.Second; remaining > limit {
		remaining = limit
	}
	// Covers input materialization and final capture as well as child execution.
	watchdog := time.AfterFunc(time.Until(now.Add(remaining)), func() { os.Exit(124) })
	defer watchdog.Stop()
	syscall.Umask(0077)
	var input *contracts.WorkspaceInput
	workspaceID := contracts.WorkspaceId(os.Getenv("INV_WORKSPACE_ID"))
	if raw := os.Getenv("INV_WORKSPACE_INPUT"); raw != "" {
		if json.Unmarshal([]byte(raw), &input) != nil || input == nil {
			return 125
		}
		snapshot, err := workspace.Input(input, workspaceID)
		if err != nil || workspace.Seed("/workspace", snapshot) != nil {
			return 125
		}
	}
	os.Unsetenv("INV_WORKSPACE_INPUT")
	os.Unsetenv("INV_WORKSPACE_ID")
	child := exec.Command(flag.Args()[0], flag.Args()[1:]...)
	child.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
	stdout, stderr := &outputBuffer{}, &outputBuffer{}
	child.Stdout, child.Stderr = stdout, stderr
	child.WaitDelay = 100 * time.Millisecond
	child.Env = []string{"PATH=/usr/bin:/bin", "HOME=/workspace"}
	if err := child.Start(); err != nil {
		return 126
	}
	completed := make(chan error, 1)
	go func() { completed <- child.Wait() }()
	timer := time.NewTimer(time.Until(now.Add(remaining)))
	defer timer.Stop()
	signals := make(chan os.Signal, 1)
	signal.Notify(signals, syscall.SIGTERM, syscall.SIGINT)
	defer signal.Stop(signals)
	select {
	case err := <-completed:
		if input != nil && err == nil {
			// Private PID namespace: no descendant may mutate files during capture.
			if err := syscall.Kill(-1, syscall.SIGKILL); err != nil && err != syscall.ESRCH {
				return 125
			}
			for {
				var status syscall.WaitStatus
				_, err := syscall.Wait4(-1, &status, 0, nil)
				if err == syscall.ECHILD {
					break
				}
				if err == syscall.EINTR {
					continue
				}
				if err != nil {
					return 125
				}
			}
			snapshot, err := workspace.Capture("/workspace", workspaceID)
			if err != nil {
				return 122
			}
			return emitWorkspaceOutput(stdout, stderr, input, snapshot)
		}
		if err == nil {
			return emitOutput(stdout, stderr, 0)
		}
		if exit, ok := err.(*exec.ExitError); ok && exit.ExitCode() >= 0 {
			return emitOutput(stdout, stderr, exit.ExitCode())
		}
		return 127
	case <-timer.C:
		_ = syscall.Kill(-child.Process.Pid, syscall.SIGKILL)
		return 124
	case <-signals:
		_ = syscall.Kill(-child.Process.Pid, syscall.SIGKILL)
		return 143
	}
}
