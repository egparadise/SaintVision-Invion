package runtime

import (
	"crypto/ed25519"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	contracts "github.com/egparadise/SaintVision-Invion/packages/contracts-go"
	"github.com/egparadise/SaintVision-Invion/services/node-agent/internal/wire"
	"strconv"
	"strings"
	"time"
)

const domain = "SaintVision.NodePermit.v1\x00"

type Config struct {
	TenantID, NodeID, Epoch, Profile, Image, Executable string
	PublicKey                                           ed25519.PublicKey
	MaxCPU, MaxMemory                                   int64
	MaxTimeout                                          time.Duration
}

type Permit struct {
	Data contracts.NodeExecutionPermit
	Hash string
}

func Verify(envelope []byte, config Config) (Permit, error) {
	var permit Permit
	if len(config.PublicKey) != ed25519.PublicKeySize || config.MaxCPU <= 0 || config.MaxMemory <= 0 || config.MaxTimeout <= 0 {
		return permit, errors.New("NODE-0005: incomplete trusted configuration")
	}
	if err := wire.Validate("SignedNodePermit", envelope); err != nil {
		return permit, err
	}
	var signed contracts.SignedNodePermit
	if err := json.Unmarshal(envelope, &signed); err != nil {
		return permit, errors.New("NODE-0003: invalid envelope")
	}
	raw, err := base64.StdEncoding.Strict().DecodeString(signed.Payload)
	if err != nil || len(raw) > 1048576 {
		return permit, errors.New("NODE-0003: invalid payload")
	}
	signature, err := base64.StdEncoding.Strict().DecodeString(signed.Signature)
	if err != nil || !ed25519.Verify(config.PublicKey, append([]byte(domain), raw...), signature) {
		return permit, errors.New("NODE-0006: signature rejected")
	}
	if err := wire.Validate("NodeExecutionPermit", raw); err != nil {
		return permit, err
	}
	if err := json.Unmarshal(raw, &permit.Data); err != nil {
		return permit, errors.New("NODE-0003: invalid typed payload")
	}
	var fields map[string]json.RawMessage
	_ = json.Unmarshal(raw, &fields)
	planHash := sha256.Sum256(fields["launch"])
	payloadHash := sha256.Sum256(raw)
	permit.Hash = hex.EncodeToString(payloadHash[:])
	claim, plan := permit.Data.Claim, permit.Data.Launch
	if string(claim.TenantId) != config.TenantID || string(claim.NodeId) != config.NodeID || claim.RecoveryEpoch != config.Epoch || claim.ProfileVersion != config.Profile || plan.ProfileVersion != config.Profile || string(claim.PlanDigest) != hex.EncodeToString(planHash[:]) {
		return permit, errors.New("NODE-0007: permit scope differs")
	}
	if plan.ImageDigest != config.Image || len(plan.Argv) == 0 || plan.Argv[0] != config.Executable || plan.CpuMillis > config.MaxCPU || plan.MemoryBytes > config.MaxMemory || plan.MemoryBytes < 8*1024*1024 || plan.TimeoutSeconds > int64(config.MaxTimeout/time.Second) {
		return permit, errors.New("NODE-0008: local sandbox policy rejected")
	}
	for _, arg := range plan.Argv {
		if strings.ContainsRune(arg, 0) {
			return permit, errors.New("NODE-0008: NUL argument rejected")
		}
	}
	seen := map[contracts.LeaseId]bool{}
	var cpu, memory int64
	deadline, err := time.Parse(time.RFC3339Nano, string(claim.NotAfter))
	if err != nil {
		return permit, errors.New("NODE-0007: invalid deadline")
	}
	for _, a := range permit.Data.Allocations {
		l := a.Lease
		expires, err := time.Parse(time.RFC3339Nano, string(l.ExpiresAt))
		parts := strings.Split(l.FencingToken, ":")
		if err != nil || seen[l.LeaseId] || a.NodeId != claim.NodeId || l.TenantId != claim.TenantId || l.RunId != claim.RunId || len(parts) != 2 || parts[0] != config.Epoch || expires.Before(deadline) {
			return permit, errors.New("NODE-0009: allocation proof rejected")
		}
		token, err := strconv.ParseUint(parts[1], 10, 63)
		if err != nil || token == 0 {
			return permit, errors.New("NODE-0009: allocation token rejected")
		}
		seen[l.LeaseId] = true
		if a.Kind == "cpu" {
			cpu += l.Amount
		} else if a.Kind == "memory" {
			memory += l.Amount
		}
	}
	if cpu < plan.CpuMillis || memory < plan.MemoryBytes {
		return permit, errors.New("NODE-0009: allocation limits insufficient")
	}
	return permit, nil
}

func (p Permit) Budget(now time.Time) (time.Duration, error) {
	deadline, _ := time.Parse(time.RFC3339Nano, string(p.Data.Claim.NotAfter))
	issued, err := time.Parse(time.RFC3339Nano, string(p.Data.IssuedAt))
	// Subtract the maximum admitted clock skew. The resulting duration is enforced
	// by Go's monotonic timer, independent of subsequent wall-clock adjustments.
	budget := deadline.Sub(now) - 5*time.Second
	if err != nil || issued.After(now.Add(5*time.Second)) || deadline.Sub(issued) > 30*time.Second || deadline.Before(issued) || budget <= 0 {
		return 0, errors.New("NODE-0010: permit expired or clock bound exceeded")
	}
	if max := time.Duration(p.Data.Launch.TimeoutSeconds) * time.Second; budget > max {
		budget = max
	}
	return budget, nil
}
