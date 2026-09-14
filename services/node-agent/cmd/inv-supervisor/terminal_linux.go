//go:build linux

package main

import (
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"errors"
	contracts "github.com/egparadise/SaintVision-Invion/packages/contracts-go"
	"github.com/egparadise/SaintVision-Invion/services/node-agent/internal/wire"
	"io"
	"net"
	"os"
	"os/exec"
	"strconv"
	"sync"
	"syscall"
	"time"
	"unsafe"
)

const terminalSocket = "/tmp/.inv-terminal.sock"

var errTerminal = errors.New("NODE-0090: terminal frame rejected")

type terminalPTY struct {
	mu                   sync.Mutex
	spec                 contracts.TerminalSpec
	command              contracts.CommandId
	master, slave        *os.File
	listener             net.Listener
	output               []byte
	inputBytes, sequence int64
	lastHash             [32]byte
	last                 *contracts.NodeTerminalResult
	poisoned             bool
	done                 chan struct{}
}

func ioctl(fd uintptr, request uintptr, value unsafe.Pointer) error {
	_, _, errno := syscall.Syscall(syscall.SYS_IOCTL, fd, request, uintptr(value))
	if errno != 0 {
		return errno
	}
	return nil
}

func resizePTY(file *os.File, rows, columns int64) error {
	if rows < 1 || rows > 200 || columns < 1 || columns > 400 {
		return errTerminal
	}
	size := [4]uint16{uint16(rows), uint16(columns), 0, 0}
	raw, err := file.SyscallConn()
	if err != nil {
		return err
	}
	var callErr error
	if err = raw.Control(func(fd uintptr) { callErr = ioctl(fd, syscall.TIOCSWINSZ, unsafe.Pointer(&size)) }); err != nil {
		return err
	}
	return callErr
}

func openTerminal(spec contracts.TerminalSpec, command contracts.CommandId, child *exec.Cmd) (*terminalPTY, error) {
	fd, err := syscall.Open("/dev/ptmx", syscall.O_RDWR|syscall.O_NOCTTY|syscall.O_CLOEXEC|syscall.O_NONBLOCK, 0)
	if err != nil {
		return nil, errTerminal
	}
	master := os.NewFile(uintptr(fd), "terminal-master")
	fail := func() (*terminalPTY, error) { master.Close(); return nil, errTerminal }
	var unlock int32
	var number uint32
	if ioctl(uintptr(fd), syscall.TIOCSPTLCK, unsafe.Pointer(&unlock)) != nil || ioctl(uintptr(fd), syscall.TIOCGPTN, unsafe.Pointer(&number)) != nil {
		return fail()
	}
	slave, err := os.OpenFile("/dev/pts/"+strconv.FormatUint(uint64(number), 10), os.O_RDWR|syscall.O_NOCTTY, 0)
	if err != nil {
		return fail()
	}
	if resizePTY(master, spec.Rows, spec.Columns) != nil {
		slave.Close()
		return fail()
	}
	// The child owns a new session and controlling terminal, within the existing
	// container PID/user/network/filesystem/resource restrictions.
	child.Stdin, child.Stdout, child.Stderr = slave, slave, slave
	child.SysProcAttr = &syscall.SysProcAttr{Setsid: true, Setctty: true, Ctty: 0}
	listener, err := net.Listen("unix", terminalSocket)
	if err != nil {
		slave.Close()
		return fail()
	}
	p := &terminalPTY{spec: spec, command: command, master: master, slave: slave, listener: listener, done: make(chan struct{})}
	return p, nil
}

func (p *terminalPTY) start(stdout *outputBuffer) {
	p.slave.Close()
	go func() {
		defer close(p.done)
		data := make([]byte, 4096)
		for {
			n, err := p.master.Read(data)
			if n > 0 {
				p.mu.Lock()
				if int64(len(p.output)+n) > p.spec.MaxOutputBytes {
					p.poisoned = true
					stdout.mutex.Lock()
					stdout.truncated = true
					stdout.mutex.Unlock()
				} else {
					p.output = append(p.output, data[:n]...)
					_, _ = stdout.Write(data[:n])
				}
				p.mu.Unlock()
			}
			if err != nil {
				return
			}
		}
	}()
	go func() {
		for {
			conn, err := p.listener.Accept()
			if err != nil {
				return
			}
			// One frame at a time, bounded deadline; no unbounded goroutine per client.
			_ = conn.SetDeadline(time.Now().Add(time.Second))
			raw, err := io.ReadAll(io.LimitReader(conn, 8193))
			if err == nil && len(raw) <= 8192 && wire.Validate("TerminalFrameInput", raw) == nil {
				var frame contracts.TerminalFrameInput
				if json.Unmarshal(raw, &frame) == nil {
					if result, err := p.frame(frame); err == nil {
						_ = json.NewEncoder(conn).Encode(result)
					}
				}
			}
			conn.Close()
		}
	}()
}

func (p *terminalPTY) frame(frame contracts.TerminalFrameInput) (*contracts.NodeTerminalResult, error) {
	p.mu.Lock()
	defer p.mu.Unlock()
	raw, _ := json.Marshal(frame)
	sum := sha256.Sum256(raw)
	if p.poisoned || frame.Cursor < 0 || frame.Cursor > int64(len(p.output)) {
		return nil, errTerminal
	}
	if frame.Operation != "poll" {
		if frame.Sequence == p.sequence && p.last != nil && sum == p.lastHash {
			copy := *p.last
			return &copy, nil
		}
		if frame.Sequence != p.sequence+1 || frame.Sequence > 4096 {
			return nil, errTerminal
		}
	} else if frame.Sequence != 0 || frame.DataBase64 != "" {
		return nil, errTerminal
	}
	data, err := base64.StdEncoding.Strict().DecodeString(frame.DataBase64)
	if err != nil || len(data) > 1024 || base64.StdEncoding.EncodeToString(data) != frame.DataBase64 {
		return nil, errTerminal
	}
	if frame.Operation == "input" {
		if len(data) == 0 || p.inputBytes+int64(len(data)) > p.spec.MaxInputBytes {
			return nil, errTerminal
		}
		// Consume before writing. A partial write is uncertain and poisons further
		// input instead of replaying bytes. Exact successful retries return last.
		p.sequence = frame.Sequence
		p.last = nil
		p.lastHash = sum
		_ = p.master.SetWriteDeadline(time.Now().Add(300 * time.Millisecond))
		n, err := p.master.Write(data)
		p.inputBytes += int64(n)
		if err != nil || n != len(data) {
			p.poisoned = true
			return nil, errTerminal
		}
	} else if frame.Operation == "resize" {
		if len(data) != 0 {
			return nil, errTerminal
		}
		p.sequence = frame.Sequence
		p.last = nil
		p.lastHash = sum
		if resizePTY(p.master, frame.Rows, frame.Columns) != nil {
			p.poisoned = true
			return nil, errTerminal
		}
	} else if frame.Operation != "poll" {
		return nil, errTerminal
	}
	end := frame.Cursor + 4096
	if end > int64(len(p.output)) {
		end = int64(len(p.output))
	}
	result := &contracts.NodeTerminalResult{CommandId: p.command, SessionId: p.spec.SessionId, Sequence: p.sequence, Cursor: end, DataBase64: base64.StdEncoding.EncodeToString(p.output[frame.Cursor:end]), Nonce: frame.Nonce}
	if frame.Operation != "poll" {
		copy := *result
		p.last = &copy
	}
	return result, nil
}

func (p *terminalPTY) finish() error {
	// Caller has already killed remaining descendants; EOF drains their last bytes.
	select {
	case <-p.done:
	case <-time.After(200 * time.Millisecond):
		return errTerminal
	}
	p.mu.Lock()
	defer p.mu.Unlock()
	if p.poisoned {
		return errTerminal
	}
	return nil
}
func (p *terminalPTY) close() { p.listener.Close(); p.slave.Close(); p.master.Close() }

// A fixed, image-owned exec helper. No command string, path or credentials are
// taken from a browser. The parent validates all fields again before PTY I/O.
func terminalFrame() int {
	if os.Geteuid() != 65532 || os.Getpid() == 1 {
		return 125
	}
	raw, err := base64.StdEncoding.Strict().DecodeString(os.Getenv("INV_TERMINAL_FRAME"))
	os.Unsetenv("INV_TERMINAL_FRAME")
	if err != nil || len(raw) > 8192 || wire.Validate("TerminalFrameInput", raw) != nil {
		return 125
	}
	conn, err := net.DialTimeout("unix", terminalSocket, 200*time.Millisecond)
	if err != nil {
		return 125
	}
	defer conn.Close()
	_ = conn.SetDeadline(time.Now().Add(700 * time.Millisecond))
	if _, err = conn.Write(raw); err != nil {
		return 125
	}
	if c, ok := conn.(*net.UnixConn); !ok || c.CloseWrite() != nil {
		return 125
	}
	result, err := io.ReadAll(io.LimitReader(conn, 16385))
	if err != nil || len(result) > 16384 || wire.Validate("NodeTerminalResult", result) != nil {
		return 125
	}
	if _, err = os.Stdout.Write(result); err != nil {
		return 125
	}
	return 0
}
