package runtime

import (
	"crypto/ed25519"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	contracts "github.com/egparadise/SaintVision-Invion/packages/contracts-go"
	"github.com/egparadise/SaintVision-Invion/services/node-agent/internal/wire"
	"strings"
	"testing"
	"time"
)

func fixture(t *testing.T) (Config, contracts.NodeExecutionPermit, ed25519.PrivateKey) {
	t.Helper()
	public, private, err := ed25519.GenerateKey(rand.Reader)
	if err != nil {
		t.Fatal(err)
	}
	config := Config{TenantID: uuid(), NodeID: "nod_" + strings.Repeat("0", 26), Epoch: uuid(), Profile: "restricted:test:1", Image: "sha256:" + strings.Repeat("a", 64), Executable: "/probe", PublicKey: public, MaxCPU: 1000, MaxMemory: 512 * 1024 * 1024, MaxTimeout: 30 * time.Second}
	now := time.Now().UTC()
	stamp := func(t time.Time) contracts.Timestamp { return contracts.Timestamp(t.Format(time.RFC3339Nano)) }
	claim := contracts.ExecutionClaim{CommandId: contracts.CommandId(uuid()), ClaimId: contracts.ClaimId(uuid()), RunId: contracts.RunId("run_" + strings.Repeat("0", 26)), TenantId: contracts.TenantId(config.TenantID), ProjectId: contracts.ProjectId("prj_" + strings.Repeat("0", 26)), NodeId: contracts.NodeId(config.NodeID), ActionDigest: contracts.ActionDigest(strings.Repeat("a", 64)), PolicyVersion: "roof:test:1", ProfileVersion: config.Profile, RecoveryEpoch: config.Epoch, NotAfter: stamp(now.Add(20 * time.Second))}
	plan := contracts.SandboxLaunchSpec{ProfileVersion: config.Profile, ImageDigest: config.Image, Argv: []string{"/probe", "synthetic-value"}, WorkspaceId: contracts.WorkspaceId("wsp_" + strings.Repeat("0", 26)), WorkingDirectory: "/workspace", WorkspaceMode: "ephemeral", CpuMillis: 500, MemoryBytes: 64 * 1024 * 1024, TimeoutSeconds: 5, PidsLimit: 64, UserId: 65532, Network: "none", RootfsReadOnly: true, CapDropAll: true, NoNewPrivileges: true}
	data := contracts.NodeExecutionPermit{Claim: claim, Launch: plan, IssuedAt: stamp(now)}
	for i, kind := range []string{"cpu", "memory"} {
		amount := int64(500)
		if kind == "memory" {
			amount = 64 * 1024 * 1024
		}
		suffix := strings.Repeat("0", 25) + string(rune('1'+i))
		data.Allocations = append(data.Allocations, contracts.NodeAllocation{NodeId: claim.NodeId, Kind: kind, Lease: contracts.ResourceLease{LeaseId: contracts.LeaseId("lse_" + suffix), TenantId: claim.TenantId, RunId: claim.RunId, ResourceId: contracts.ResourceId("res_" + suffix), Amount: amount, FencingToken: config.Epoch + ":1", GrantedAt: stamp(now.Add(-time.Second)), ExpiresAt: stamp(now.Add(time.Minute))}})
	}
	return config, data, private
}
func signedRaw(t *testing.T, raw []byte, key ed25519.PrivateKey) []byte {
	t.Helper()
	result, err := json.Marshal(contracts.SignedNodePermit{Payload: base64.StdEncoding.EncodeToString(raw), Signature: base64.StdEncoding.EncodeToString(ed25519.Sign(key, append([]byte(domain), raw...)))})
	if err != nil {
		t.Fatal(err)
	}
	return result
}
func signed(t *testing.T, data contracts.NodeExecutionPermit, key ed25519.PrivateKey) []byte {
	t.Helper()
	plan, _ := json.Marshal(data.Launch)
	hash := sha256.Sum256(plan)
	data.Claim.PlanDigest = contracts.ActionDigest(hex.EncodeToString(hash[:]))
	raw, err := json.Marshal(data)
	if err != nil {
		t.Fatal(err)
	}
	return signedRaw(t, raw, key)
}
func TestValidPermitAndBoundBudget(t *testing.T) {
	config, data, key := fixture(t)
	p, err := Verify(signed(t, data, key), config)
	if err != nil {
		t.Fatal(err)
	}
	budget, err := p.Budget(time.Now())
	if err != nil || budget != 5*time.Second {
		t.Fatalf("budget %v: %v", budget, err)
	}
}
func TestPermitRejectsBoundaryViolations(t *testing.T) {
	cases := map[string]func(*Config, *contracts.NodeExecutionPermit){
		"wrong-key":    func(c *Config, p *contracts.NodeExecutionPermit) { c.PublicKey = make([]byte, 32) },
		"other-tenant": func(c *Config, p *contracts.NodeExecutionPermit) { c.TenantID = uuid() },
		"other-node":   func(c *Config, p *contracts.NodeExecutionPermit) { c.NodeID = "nod_" + strings.Repeat("1", 26) },
		"old-epoch":    func(c *Config, p *contracts.NodeExecutionPermit) { c.Epoch = uuid() },
		"unapproved-image": func(c *Config, p *contracts.NodeExecutionPermit) {
			p.Launch.ImageDigest = "sha256:" + strings.Repeat("b", 64)
		},
		"unapproved-executable": func(c *Config, p *contracts.NodeExecutionPermit) { p.Launch.Argv[0] = "/bin/sh" },
		"host-network":          func(c *Config, p *contracts.NodeExecutionPermit) { p.Launch.Network = "host" },
		"root":                  func(c *Config, p *contracts.NodeExecutionPermit) { p.Launch.UserId = 0 },
		"writable-root":         func(c *Config, p *contracts.NodeExecutionPermit) { p.Launch.RootfsReadOnly = false },
		"capabilities":          func(c *Config, p *contracts.NodeExecutionPermit) { p.Launch.CapDropAll = false },
		"privilege":             func(c *Config, p *contracts.NodeExecutionPermit) { p.Launch.Privileged = true },
		"insufficient-cpu":      func(c *Config, p *contracts.NodeExecutionPermit) { p.Allocations[0].Lease.Amount = 499 },
		"insufficient-memory":   func(c *Config, p *contracts.NodeExecutionPermit) { p.Allocations[1].Lease.Amount = 1 },
		"duplicate-lease": func(c *Config, p *contracts.NodeExecutionPermit) {
			p.Allocations = append(p.Allocations, p.Allocations[0])
		},
		"short-lease": func(c *Config, p *contracts.NodeExecutionPermit) { p.Allocations[0].Lease.ExpiresAt = p.IssuedAt },
		"wrong-allocation-node": func(c *Config, p *contracts.NodeExecutionPermit) {
			p.Allocations[0].NodeId = contracts.NodeId("nod_" + strings.Repeat("1", 26))
		},
		"wrong-allocation-epoch": func(c *Config, p *contracts.NodeExecutionPermit) { p.Allocations[0].Lease.FencingToken = uuid() + ":1" },
		"token-overflow": func(c *Config, p *contracts.NodeExecutionPermit) {
			p.Allocations[0].Lease.FencingToken = c.Epoch + ":99999999999999999999999"
		},
		"local-limits": func(c *Config, p *contracts.NodeExecutionPermit) { c.MaxMemory = 1024 },
		"nul-argument": func(c *Config, p *contracts.NodeExecutionPermit) {
			p.Launch.Argv = append(p.Launch.Argv, "hidden\x00value")
		},
	}
	for name, change := range cases {
		t.Run(name, func(t *testing.T) {
			c, p, k := fixture(t)
			change(&c, &p)
			if _, err := Verify(signed(t, p, k), c); err == nil {
				t.Fatal("unsafe permit accepted")
			}
		})
	}
}
func TestByteBindingAndStrictJSON(t *testing.T) {
	c, p, k := fixture(t)
	envelope := signed(t, p, k)
	var e contracts.SignedNodePermit
	_ = json.Unmarshal(envelope, &e)
	raw, _ := base64.StdEncoding.DecodeString(e.Payload)
	for name, value := range map[string][]byte{
		"tampered-plan": []byte(strings.Replace(string(raw), "synthetic-value", "changed", 1)),
		"duplicate-key": append([]byte(`{"issuedAt":"2020-01-01T00:00:00Z",`), raw[1:]...),
		"unknown-field": append([]byte(`{"unknown":true,`), raw[1:]...),
	} {
		t.Run(name, func(t *testing.T) {
			if _, err := Verify(signedRaw(t, value, k), c); err == nil {
				t.Fatal("invalid signed bytes accepted")
			}
		})
	}
	for _, raw := range []string{`{"a":1,"a":2}`, `{} {}`, `{"n":NaN}`, strings.Repeat("[", 65) + strings.Repeat("]", 65)} {
		if wire.StrictJSON([]byte(raw)) == nil {
			t.Fatal("ambiguous JSON accepted")
		}
	}
}
func TestClockBounds(t *testing.T) {
	c, p, k := fixture(t)
	v, err := Verify(signed(t, p, k), c)
	if err != nil {
		t.Fatal(err)
	}
	for _, now := range []time.Time{time.Now().Add(16 * time.Second), time.Now().Add(-6 * time.Second), time.Now().Add(time.Hour)} {
		if _, err := v.Budget(now); err == nil {
			t.Fatal("unsafe clock admitted")
		}
	}
}
