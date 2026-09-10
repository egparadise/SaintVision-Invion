package runtime

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/base64"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	contracts "github.com/egparadise/SaintVision-Invion/packages/contracts-go"
	"io"
	"net"
	"net/http"
	"net/url"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"time"
)

var ErrAbsent = errors.New("NODE-0020: container not found; execution remains uncertain")
var ErrEngineUnavailable = errors.New("NODE-0022: engine unavailable")
var hexID = regexp.MustCompile(`^[0-9a-f]{64}$`)

type State struct {
	ID                  string
	Running, Restarting bool
	PID, ExitCode       int
	StartedAt, Status   string
}
type Engine interface {
	Create(context.Context, Record, contracts.SandboxLaunchSpec) (string, error)
	Start(context.Context, string) error
	Inspect(context.Context, string, Record) (State, error)
	Stop(context.Context, string) error
	Remove(context.Context, string, Record) error
	Output(context.Context, string, Record) (*contracts.NodeOutput, error)
}
type Docker struct{ client *http.Client }

// Only a locally configured Unix socket is supported. Neither permit data nor
// inherited DOCKER_HOST/proxy credentials can redirect this privileged connection.
func NewDocker(socket string) (*Docker, error) {
	if !filepath.IsAbs(socket) || filepath.Clean(socket) != socket {
		return nil, errors.New("NODE-0021: absolute local Docker socket required")
	}
	transport := &http.Transport{Proxy: nil, DialContext: func(ctx context.Context, _, _ string) (net.Conn, error) {
		return (&net.Dialer{}).DialContext(ctx, "unix", socket)
	}}
	return &Docker{client: &http.Client{Transport: transport, Timeout: 2 * time.Second, CheckRedirect: func(req *http.Request, via []*http.Request) error { return errors.New("redirect refused") }}}, nil
}
func (d *Docker) request(ctx context.Context, method, path string, body any, out any) error {
	var reader io.Reader
	if body != nil {
		data, err := json.Marshal(body)
		if err != nil {
			return err
		}
		reader = bytes.NewReader(data)
	}
	req, err := http.NewRequestWithContext(ctx, method, "http://docker/v1.45"+path, reader)
	if err != nil {
		return errors.New("NODE-0021: invalid engine request")
	}
	req.Header.Set("Content-Type", "application/json")
	response, err := d.client.Do(req)
	if err != nil {
		return ErrEngineUnavailable
	}
	defer response.Body.Close()
	if response.StatusCode == 404 {
		return ErrAbsent
	}
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		if response.StatusCode >= 500 {
			return fmt.Errorf("%w: status %d", ErrEngineUnavailable, response.StatusCode)
		}
		return fmt.Errorf("NODE-0022: engine status %d", response.StatusCode)
	}
	if out == nil {
		_, _ = io.Copy(io.Discard, io.LimitReader(response.Body, 4096))
		return nil
	}
	decoder := json.NewDecoder(io.LimitReader(response.Body, 2*1024*1024))
	if err = decoder.Decode(out); err != nil {
		return errors.New("NODE-0022: invalid engine response")
	}
	return nil
}
func labels(r Record) map[string]string {
	return map[string]string{"ai.saintvision.node": string(r.Claim.NodeId), "ai.saintvision.tenant": string(r.Claim.TenantId), "ai.saintvision.command": string(r.Claim.CommandId), "ai.saintvision.plan": string(r.Claim.PlanDigest), "ai.saintvision.epoch": r.Claim.RecoveryEpoch}
}

func (d *Docker) Create(ctx context.Context, r Record, p contracts.SandboxLaunchSpec) (string, error) {
	var image struct {
		ID     string `json:"Id"`
		Config struct {
			Volumes map[string]any
			Labels  map[string]string
		}
	}
	if err := d.request(ctx, "GET", "/images/"+url.PathEscape(p.ImageDigest)+"/json", nil, &image); err != nil {
		return "", err
	}
	if image.ID != p.ImageDigest || len(image.Config.Volumes) != 0 || image.Config.Labels["ai.saintvision.supervisor"] != "deadline-v1" || image.Config.Labels["ai.saintvision.output"] != "bounded-streams-v1" {
		return "", errors.New("NODE-0023: image must be local pinned content without declared volumes")
	}
	environment := []string{}
	if p.WorkspaceInput != nil {
		if image.Config.Labels["ai.saintvision.workspace"] != "snapshot-tmpfs-v1" {
			return "", errors.New("NODE-0081: image lacks verified Workspace supervisor")
		}
		input, err := json.Marshal(p.WorkspaceInput)
		if err != nil {
			return "", err
		}
		environment = []string{"INV_WORKSPACE_INPUT=" + string(input), "INV_WORKSPACE_ID=" + string(p.WorkspaceId)}
	}
	if p.Terminal != nil {
		if p.WorkspaceInput == nil || image.Config.Labels["ai.saintvision.terminal"] != "pty-v1" {
			return "", errors.New("NODE-0090: approved terminal image required")
		}
		terminal, err := json.Marshal(p.Terminal)
		if err != nil {
			return "", err
		}
		environment = append(environment, "INV_TERMINAL_SPEC="+string(terminal), "INV_TERMINAL_COMMAND="+string(r.Claim.CommandId))
	}
	tmpfs := map[string]string{"/workspace": "rw,nosuid,nodev,noexec,size=16777216,uid=65532,gid=65532,mode=0700", "/tmp": "rw,nosuid,nodev,noexec,size=16777216,uid=65532,gid=65532,mode=0700"}
	host := map[string]any{"NetworkMode": "none", "ReadonlyRootfs": true, "CapDrop": []string{"ALL"}, "SecurityOpt": []string{"no-new-privileges:true"}, "Privileged": false,
		"PidsLimit": int64(64), "Memory": p.MemoryBytes, "MemorySwap": p.MemoryBytes, "NanoCpus": p.CpuMillis * 1000000, "Tmpfs": tmpfs, "AutoRemove": false,
		"IpcMode": "private", "CgroupnsMode": "private", "RestartPolicy": map[string]any{"Name": "no"}, "LogConfig": map[string]any{"Type": "local", "Config": map[string]string{"max-size": "512k", "max-file": "1", "compress": "false"}}}
	command := append([]string{"--not-after", string(r.Claim.NotAfter), "--timeout", strconv.FormatInt(p.TimeoutSeconds, 10), "--"}, p.Argv...)
	config := map[string]any{"Image": p.ImageDigest, "Entrypoint": []string{"/inv-supervisor"}, "Cmd": command, "User": "65532:65532", "WorkingDir": "/workspace", "Env": environment,
		"Labels": labels(r), "NetworkDisabled": true, "AttachStdout": false, "AttachStderr": false, "OpenStdin": false, "Tty": false, "HostConfig": host}
	var result struct {
		ID string `json:"Id"`
	}
	if err := d.request(ctx, "POST", "/containers/create?name="+url.QueryEscape(r.Name), config, &result); err != nil {
		return "", err
	}
	if !hexID.MatchString(result.ID) {
		return "", errors.New("NODE-0022: invalid container ID")
	}
	// Verify actual daemon configuration before any process can start.
	var actual inspection
	if err := d.request(ctx, "GET", "/containers/"+result.ID+"/json", nil, &actual); err != nil {
		return "", err
	}
	if err := owned(actual, r); err != nil {
		return "", err
	}
	h := actual.HostConfig
	// Images may define benign defaults. The two private input variables must
	// match exactly; duplicates or unexpected Workspace variables are rejected.
	workspaceEnv := []string{}
	for _, v := range actual.Config.Env {
		if strings.HasPrefix(v, "INV_WORKSPACE_") || strings.HasPrefix(v, "INV_TERMINAL_") {
			workspaceEnv = append(workspaceEnv, v)
		}
	}
	if !equal(workspaceEnv, environment) {
		return "", errors.New("NODE-0081: Workspace input differs")
	}
	if actual.Image != p.ImageDigest || actual.Config.User != "65532:65532" || actual.Config.WorkingDir != "/workspace" || !equal(actual.Config.Entrypoint, []string{"/inv-supervisor"}) || !equal(actual.Config.Cmd, command) ||
		h.NetworkMode != "none" || !h.ReadonlyRootfs || h.Privileged || h.Memory != p.MemoryBytes || h.MemorySwap != p.MemoryBytes || h.NanoCpus != p.CpuMillis*1000000 || h.PidsLimit != 64 ||
		!equal(h.CapDrop, []string{"ALL"}) || !(equal(h.SecurityOpt, []string{"no-new-privileges:true"}) || equal(h.SecurityOpt, []string{"no-new-privileges"})) ||
		len(h.Binds) != 0 || len(h.Devices) != 0 || len(h.DeviceRequests) != 0 || len(h.PortBindings) != 0 || h.PidMode != "" || h.IpcMode != "private" || h.UTSMode != "" || h.CgroupnsMode != "private" || h.AutoRemove || h.RestartPolicy.Name != "no" || h.LogConfig.Type != "local" || h.LogConfig.Config["max-size"] != "512k" || h.LogConfig.Config["max-file"] != "1" || h.LogConfig.Config["compress"] != "false" || len(h.Tmpfs) != 2 {
		return "", errors.New("NODE-0024: daemon isolation configuration differs")
	}
	for path, options := range tmpfs {
		if h.Tmpfs[path] != options {
			return "", errors.New("NODE-0024: tmpfs configuration differs")
		}
	}
	return result.ID, nil
}
func equal(a, b []string) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}

type inspection struct {
	ID          string `json:"Id"`
	Name, Image string
	Config      struct {
		User, WorkingDir     string
		Entrypoint, Cmd, Env []string
		Labels               map[string]string
	}
	HostConfig struct {
		NetworkMode                             string
		ReadonlyRootfs, Privileged, AutoRemove  bool
		Memory, MemorySwap, NanoCpus, PidsLimit int64
		CapDrop, SecurityOpt, Binds             []string
		Devices, DeviceRequests                 []any
		PortBindings                            map[string]any
		Tmpfs                                   map[string]string
		PidMode, IpcMode, UTSMode, CgroupnsMode string
		RestartPolicy                           struct{ Name string }
		LogConfig                               struct {
			Type   string
			Config map[string]string
		}
	}
	State struct {
		Running, Restarting bool
		Pid, ExitCode       int
		StartedAt, Status   string
	}
}

func owned(value inspection, r Record) error {
	if !hexID.MatchString(value.ID) || strings.TrimPrefix(value.Name, "/") != r.Name {
		return errors.New("NODE-0025: container identity differs")
	}
	for key, wanted := range labels(r) {
		if value.Config.Labels[key] != wanted {
			return errors.New("NODE-0025: container ownership differs")
		}
	}
	return nil
}
func (d *Docker) Start(ctx context.Context, id string) error {
	if !hexID.MatchString(id) {
		return errors.New("NODE-0025: invalid container ID")
	}
	return d.request(ctx, "POST", "/containers/"+id+"/start", nil, nil)
}
func (d *Docker) Inspect(ctx context.Context, name string, r Record) (State, error) {
	var actual inspection
	if name != r.Name && !hexID.MatchString(name) {
		return State{}, errors.New("NODE-0025: invalid container identity")
	}
	if err := d.request(ctx, "GET", "/containers/"+url.PathEscape(name)+"/json", nil, &actual); err != nil {
		return State{}, err
	}
	if err := owned(actual, r); err != nil {
		return State{}, err
	}
	return State{ID: actual.ID, Running: actual.State.Running, Restarting: actual.State.Restarting, PID: actual.State.Pid, ExitCode: actual.State.ExitCode, StartedAt: actual.State.StartedAt, Status: actual.State.Status}, nil
}
func (d *Docker) Stop(ctx context.Context, id string) error {
	if !hexID.MatchString(id) {
		return errors.New("NODE-0025: invalid container ID")
	}
	return d.request(ctx, "POST", "/containers/"+id+"/stop?t=0", nil, nil)
}
func (d *Docker) Remove(ctx context.Context, id string, r Record) error {
	state, err := d.Inspect(ctx, id, r)
	if err != nil {
		return err
	}
	if !stopped(state) {
		return errors.New("NODE-0026: refuse to remove unconfirmed running container")
	}
	return d.request(ctx, "DELETE", "/containers/"+id+"?force=false&v=true", nil, nil)
}
func stopped(s State) bool {
	return !s.Running && !s.Restarting && s.PID == 0 && (s.Status == "exited" || s.Status == "created")
}

func (d *Docker) Output(ctx context.Context, id string, r Record) (*contracts.NodeOutput, error) {
	state, err := d.Inspect(ctx, id, r)
	if err != nil || !stopped(state) {
		return nil, errors.New("NODE-0070: output requires stopped owned container")
	}
	req, err := http.NewRequestWithContext(ctx, "GET", "http://docker/v1.45/containers/"+id+"/logs?stdout=true&stderr=true&follow=false", nil)
	if err != nil {
		return nil, err
	}
	response, err := d.client.Do(req)
	if err != nil {
		return nil, errors.New("NODE-0070: output unavailable")
	}
	defer response.Body.Close()
	if response.StatusCode != 200 {
		return nil, errors.New("NODE-0070: output unavailable")
	}
	// Docker multiplexes stdout/stderr into 8-byte framed records. PID 1 emits
	// exactly one JSON artifact on stdout; daemon diagnostics are never accepted.
	reader := io.LimitReader(response.Body, 400001)
	var data []byte
	for {
		header := make([]byte, 8)
		n, err := io.ReadFull(reader, header)
		if err == io.EOF && n == 0 {
			break
		}
		if err != nil || header[0] != 1 || header[1] != 0 || header[2] != 0 || header[3] != 0 {
			return nil, errors.New("NODE-0070: invalid output frame")
		}
		size := int(binary.BigEndian.Uint32(header[4:]))
		if size > 300000-len(data) {
			return nil, errors.New("NODE-0070: output exceeds bounds")
		}
		frame := make([]byte, size)
		if _, err = io.ReadFull(reader, frame); err != nil {
			return nil, errors.New("NODE-0070: incomplete output")
		}
		data = append(data, frame...)
	}
	if len(data) == 0 {
		return nil, errors.New("NODE-0070: output missing")
	}
	sum := sha256.Sum256(data)
	return &contracts.NodeOutput{Data: base64.StdEncoding.EncodeToString(data), Sha256: hex.EncodeToString(sum[:]), SizeBytes: int64(len(data))}, nil
}
