//go:build linux

package runtime

// A read-only observer deliberately does not call OpenJournal: the serving
// process retains its flock, and missing state must never be initialized.
import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
	"unicode/utf8"

	"github.com/egparadise/SaintVision-Invion/services/node-agent/internal/wire"
)

const MaxPeerPolicyVersion int64 = 9007199254740991

type PeerPolicyFloorObservation struct {
	Version               int64
	Hash                  string
	FloorSHA256           string
	JournalIdentitySHA256 string
	JournalUID            uint32
}

var peerFloorUnavailable = errors.New("NODE-0041: actual peer policy floor observation unavailable")

// Hash descriptor bytes of the actual owned serving executable. This is
// deliberately distinct from the raw /proc cmdline hash and image digest.
func ServingExecutableSHA256(pid int, uid uint32) (string, error) {
	if pid < 1 {
		return "", peerFloorUnavailable
	}
	base := fmt.Sprintf("/proc/%d", pid)
	start := func() (string, error) {
		info, err := os.Stat(base)
		if err != nil {
			return "", peerFloorUnavailable
		}
		owner, ok := info.Sys().(*syscall.Stat_t)
		if !ok || owner.Uid != uid {
			return "", peerFloorUnavailable
		}
		raw, err := os.ReadFile(base + "/stat")
		end := bytes.LastIndexByte(raw, ')')
		if err != nil || end < 1 {
			return "", peerFloorUnavailable
		}
		fields := strings.Fields(string(raw[end+1:]))
		if len(fields) < 20 {
			return "", peerFloorUnavailable
		}
		if _, err := strconv.ParseUint(fields[19], 10, 64); err != nil {
			return "", peerFloorUnavailable
		}
		return fields[19], nil
	}
	firstStart, err := start()
	if err != nil {
		return "", err
	}
	f, err := os.Open(base + "/exe") // intentional kernel proc descriptor link
	if err != nil {
		return "", peerFloorUnavailable
	}
	defer f.Close()
	before, err := f.Stat()
	self, selfErr := os.Stat("/proc/self/exe")
	if err != nil || selfErr != nil || !before.Mode().IsRegular() || !os.SameFile(before, self) || before.Size() < 1 || before.Size() > 128*1024*1024 {
		return "", peerFloorUnavailable
	}
	metadata, ok := before.Sys().(*syscall.Stat_t)
	if !ok || metadata.Uid != uid || metadata.Mode&0022 != 0 {
		return "", peerFloorUnavailable
	}
	h := sha256.New()
	n, err := io.Copy(h, io.LimitReader(f, 128*1024*1024+1))
	after, statErr := f.Stat()
	current, currentErr := os.Stat(base + "/exe")
	lastStart, startErr := start()
	if err != nil || n != before.Size() || statErr != nil || currentErr != nil || startErr != nil || firstStart != lastStart || !os.SameFile(before, after) || !os.SameFile(before, current) {
		return "", peerFloorUnavailable
	}
	last, ok := after.Sys().(*syscall.Stat_t)
	if !ok || metadata.Size != last.Size || metadata.Mode != last.Mode || metadata.Uid != last.Uid || metadata.Gid != last.Gid || metadata.Nlink != last.Nlink || metadata.Mtim != last.Mtim || metadata.Ctim != last.Ctim {
		return "", peerFloorUnavailable
	}
	named, ok := current.Sys().(*syscall.Stat_t)
	if !ok || named.Size != metadata.Size || named.Mode != metadata.Mode || named.Uid != metadata.Uid || named.Gid != metadata.Gid || named.Nlink != metadata.Nlink || named.Mtim != metadata.Mtim || named.Ctim != metadata.Ctim {
		return "", peerFloorUnavailable
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}

// Bind the observation to the real serving process, not caller-supplied policy
// data. Production container observers use PID 1; native fixtures use their real
// spawned inv-node PID. Both must run this exact executable and journal identity.
func PeerFloorServingProcess(pid int, state, policy string, config Config, uid uint32) (string, error) {
	if pid < 1 {
		return "", peerFloorUnavailable
	}
	base := fmt.Sprintf("/proc/%d", pid)
	info, err := os.Stat(base)
	if err != nil {
		return "", peerFloorUnavailable
	}
	owner, ok := info.Sys().(*syscall.Stat_t)
	if !ok || owner.Uid != uid {
		return "", peerFloorUnavailable
	}
	serving, err := os.Stat(base + "/exe")
	if err != nil {
		return "", peerFloorUnavailable
	}
	self, err := os.Stat("/proc/self/exe")
	if err != nil || !os.SameFile(serving, self) {
		return "", peerFloorUnavailable
	}
	raw, err := os.ReadFile(base + "/cmdline")
	if err != nil || len(raw) == 0 || len(raw) > 65536 || raw[len(raw)-1] != 0 || !utf8.Valid(raw) {
		return "", peerFloorUnavailable
	}
	args := strings.Split(strings.TrimSuffix(string(raw), "\x00"), "\x00")
	serve := 0
	for _, arg := range args {
		name := strings.TrimLeft(strings.SplitN(arg, "=", 2)[0], "-")
		if name == "serve" && arg != "--serve" || name == "recover" || name == "permit" || name == "observe-peer-policy-floor" {
			return "", peerFloorUnavailable
		}
		if arg == "--serve" {
			serve++
		}
		if strings.TrimLeft(strings.SplitN(arg, "=", 2)[0], "-") == "storage-policy" {
			return "", peerFloorUnavailable
		}
	}
	if serve != 1 {
		return "", peerFloorUnavailable
	}
	parent := filepath.Dir(state)
	for flag, expected := range map[string]string{"--tenant": config.TenantID, "--node": config.NodeID, "--epoch": config.Epoch, "--state": state, "--peer-policy": policy, "--tls-cert": filepath.Join(parent, "node-cert.pem"), "--tls-key": filepath.Join(parent, "node-key.pem"), "--client-ca": filepath.Join(parent, "ca.pem"), "--public-key": filepath.Join(parent, "signer.pub")} {
		count := 0
		for i, arg := range args {
			if strings.TrimLeft(strings.SplitN(arg, "=", 2)[0], "-") == strings.TrimPrefix(flag, "--") && arg != flag {
				return "", peerFloorUnavailable
			}
			if arg == flag {
				count++
				if i+1 >= len(args) || args[i+1] != expected {
					return "", peerFloorUnavailable
				}
			}
		}
		if count != 1 {
			return "", peerFloorUnavailable
		}
	}
	profiles, sockets := 0, 0
	for i, arg := range args {
		name := strings.TrimLeft(strings.SplitN(arg, "=", 2)[0], "-")
		if name == "profile" {
			profiles++
			if arg != "--profile" || i+1 >= len(args) || (args[i+1] != "lan-observe-v1" && args[i+1] != "lan-test-v1" && args[i+1] != "lan-workspace-v1") {
				return "", peerFloorUnavailable
			}
		}
		if name == "socket" {
			sockets++
			if arg != "--socket" || i+1 >= len(args) || args[i+1] != "/var/run/docker.sock" {
				return "", peerFloorUnavailable
			}
		}
	}
	if profiles != 1 || sockets > 1 {
		return "", peerFloorUnavailable
	}
	mounts, err := os.ReadFile("/proc/self/mountinfo")
	if err != nil {
		return "", peerFloorUnavailable
	}
	for _, line := range strings.Split(string(mounts), "\n") {
		fields := strings.Fields(line)
		if len(fields) > 4 && (fields[4] == "/contribution" || strings.HasPrefix(fields[4], "/contribution/")) {
			return "", peerFloorUnavailable
		}
	}
	digest := sha256.Sum256(raw)
	return hex.EncodeToString(digest[:]), nil
}

func strictObject(raw []byte, names ...string) (map[string]json.RawMessage, error) {
	d := json.NewDecoder(bytes.NewReader(raw))
	t, err := d.Token()
	if err != nil || t != json.Delim('{') {
		return nil, peerFloorUnavailable
	}
	result := map[string]json.RawMessage{}
	for d.More() {
		key, err := d.Token()
		name, ok := key.(string)
		if err != nil || !ok {
			return nil, peerFloorUnavailable
		}
		if _, duplicate := result[name]; duplicate {
			return nil, peerFloorUnavailable
		}
		var value json.RawMessage
		if d.Decode(&value) != nil {
			return nil, peerFloorUnavailable
		}
		result[name] = value
	}
	if _, err = d.Token(); err != nil {
		return nil, peerFloorUnavailable
	}
	if _, err = d.Token(); err != io.EOF {
		return nil, peerFloorUnavailable
	}
	if len(result) != len(names) {
		return nil, peerFloorUnavailable
	}
	for _, name := range names {
		if _, ok := result[name]; !ok {
			return nil, peerFloorUnavailable
		}
	}
	return result, nil
}

func existingDirectory(path string) (*os.File, syscall.Stat_t, error) {
	var info syscall.Stat_t
	if !filepath.IsAbs(path) || filepath.Clean(path) != path {
		return nil, info, peerFloorUnavailable
	}
	fd, err := syscall.Open("/", syscall.O_RDONLY|syscall.O_DIRECTORY|syscall.O_CLOEXEC, 0)
	if err != nil {
		return nil, info, peerFloorUnavailable
	}
	for _, part := range strings.Split(strings.TrimPrefix(path, "/"), "/") {
		if part == "" {
			continue
		}
		next, e := syscall.Openat(fd, part, syscall.O_RDONLY|syscall.O_DIRECTORY|syscall.O_NOFOLLOW|syscall.O_CLOEXEC, 0)
		syscall.Close(fd)
		if e != nil {
			return nil, info, peerFloorUnavailable
		}
		fd = next
	}
	if syscall.Fstat(fd, &info) != nil {
		syscall.Close(fd)
		return nil, info, peerFloorUnavailable
	}
	return os.NewFile(uintptr(fd), path), info, nil
}

func observedEntry(directory *os.File, name string, uid uint32) ([]byte, error) {
	fd, err := syscall.Openat(int(directory.Fd()), name, syscall.O_RDONLY|syscall.O_NOFOLLOW|syscall.O_NONBLOCK|syscall.O_CLOEXEC, 0)
	if err != nil {
		return nil, peerFloorUnavailable
	}
	f := os.NewFile(uintptr(fd), name)
	defer f.Close()
	var before, after, named syscall.Stat_t
	if syscall.Fstat(fd, &before) != nil || before.Mode&syscall.S_IFMT != syscall.S_IFREG || before.Mode&07777 != 0600 || before.Uid != uid || before.Nlink != 1 || before.Size < 1 || before.Size > 65536 {
		return nil, peerFloorUnavailable
	}
	raw, err := io.ReadAll(io.LimitReader(f, 65537))
	if err != nil || int64(len(raw)) != before.Size || syscall.Fstat(fd, &after) != nil ||
		before.Dev != after.Dev || before.Ino != after.Ino || before.Size != after.Size || before.Mode != after.Mode ||
		before.Uid != after.Uid || before.Gid != after.Gid || before.Nlink != after.Nlink || before.Mtim != after.Mtim || before.Ctim != after.Ctim {
		return nil, peerFloorUnavailable
	}
	// An atomic rename is either seen coherently or refused; never steal the
	// serving process's journal lock to obtain this observation.
	check, err := syscall.Openat(int(directory.Fd()), name, syscall.O_RDONLY|syscall.O_NOFOLLOW|syscall.O_NONBLOCK|syscall.O_CLOEXEC, 0)
	if err != nil {
		return nil, peerFloorUnavailable
	}
	defer syscall.Close(check)
	if syscall.Fstat(check, &named) != nil || named.Dev != before.Dev || named.Ino != before.Ino || named.Size != before.Size || named.Mtim != before.Mtim || named.Ctim != before.Ctim || named.Uid != before.Uid || named.Mode != before.Mode {
		return nil, peerFloorUnavailable
	}
	return raw, nil
}

func ReadPeerPolicyFloor(state, policyPath string, config Config) (PeerPolicyFloorObservation, error) {
	var result PeerPolicyFloorObservation
	if policyPath != filepath.Join(filepath.Dir(state), "peer-policy.json") {
		return result, peerFloorUnavailable
	}
	directory, info, err := existingDirectory(state)
	if err != nil {
		return result, err
	}
	defer directory.Close()
	if info.Mode&07777 != 0700 {
		return result, peerFloorUnavailable
	}
	parent, _, err := existingDirectory(filepath.Dir(state))
	if err != nil {
		return result, err
	}
	defer parent.Close()
	var firstFloor, firstIdentity, firstPolicy []byte
	for attempt := 0; attempt < 2; attempt++ {
		floor, err := observedEntry(directory, ".peer-policy", info.Uid)
		if err != nil {
			return result, err
		}
		identity, err := observedEntry(directory, "identity.json", info.Uid)
		if err != nil {
			return result, err
		}
		policy, err := observedEntry(parent, "peer-policy.json", info.Uid)
		if err != nil {
			return result, err
		}
		if attempt == 0 {
			firstFloor, firstIdentity, firstPolicy = floor, identity, policy
		} else if !bytes.Equal(floor, firstFloor) || !bytes.Equal(identity, firstIdentity) || !bytes.Equal(policy, firstPolicy) {
			return result, peerFloorUnavailable
		}
	}
	identity, err := strictObject(firstIdentity, "Tenant", "Node", "Epoch")
	if err != nil {
		return result, err
	}
	for name, expected := range map[string]string{"Tenant": config.TenantID, "Node": config.NodeID, "Epoch": config.Epoch} {
		var value string
		if json.Unmarshal(identity[name], &value) != nil || value != expected {
			return result, peerFloorUnavailable
		}
	}
	floor, err := strictObject(firstFloor, "Version", "Hash")
	if err != nil {
		return result, err
	}
	versionText := string(floor["Version"])
	version, err := strconv.ParseInt(versionText, 10, 64)
	if err != nil || version < 1 || version > MaxPeerPolicyVersion || strconv.FormatInt(version, 10) != versionText {
		return result, peerFloorUnavailable
	}
	var hash string
	if json.Unmarshal(floor["Hash"], &hash) != nil || !hexID.MatchString(hash) {
		return result, peerFloorUnavailable
	}
	policy, err := strictObject(firstPolicy, "version", "tenantId", "nodeId", "recoveryEpoch", "expiresAt", "clientFingerprints")
	if err != nil || wire.Validate("NodePeerPolicy", firstPolicy) != nil || string(policy["version"]) != versionText {
		return result, peerFloorUnavailable
	}
	for name, expected := range map[string]string{"tenantId": config.TenantID, "nodeId": config.NodeID, "recoveryEpoch": config.Epoch} {
		var value string
		if json.Unmarshal(policy[name], &value) != nil || value != expected {
			return result, peerFloorUnavailable
		}
	}
	digest := func(raw []byte) string { h := sha256.Sum256(raw); return hex.EncodeToString(h[:]) }
	if digest(firstPolicy) != hash {
		return result, peerFloorUnavailable
	}
	current, currentInfo, err := existingDirectory(state)
	if err != nil {
		return result, err
	}
	current.Close()
	if currentInfo.Dev != info.Dev || currentInfo.Ino != info.Ino || currentInfo.Uid != info.Uid || currentInfo.Mode != info.Mode {
		return result, peerFloorUnavailable
	}
	return PeerPolicyFloorObservation{version, hash, digest(firstFloor), digest(firstIdentity), info.Uid}, nil
}
