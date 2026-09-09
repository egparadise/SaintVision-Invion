package transport

import (
	"crypto/sha256"
	"crypto/tls"
	"crypto/x509"
	"encoding/hex"
	"encoding/json"
	"errors"
	contracts "github.com/egparadise/SaintVision-Invion/packages/contracts-go"
	"github.com/egparadise/SaintVision-Invion/services/node-agent/internal/wire"
	node "github.com/egparadise/SaintVision-Invion/services/node-agent/runtime"
	"os"
	"runtime"
	"sync"
	"time"
)

func Identity(tenant, nodeID, epoch string) string {
	return "spiffe://saintvision.ai/tenant/" + tenant + "/node/" + nodeID + "/epoch/" + epoch
}
func ControlIdentity(tenant, epoch string) string {
	return "spiffe://saintvision.ai/tenant/" + tenant + "/control-plane/epoch/" + epoch
}
func SafeFile(path string, secret bool) ([]byte, error) {
	info, err := os.Lstat(path)
	mask := os.FileMode(0022)
	if secret {
		mask = 0077
	}
	if err != nil || !info.Mode().IsRegular() || info.Size() > 65536 || (runtime.GOOS == "linux" && info.Mode().Perm()&mask != 0) {
		return nil, errors.New("NODE-0042: trusted TLS file unavailable")
	}
	data, err := os.ReadFile(path)
	if err != nil || len(data) > 65536 {
		return nil, errors.New("NODE-0042: trusted TLS file unavailable")
	}
	return data, nil
}

type Authority struct {
	mutex      sync.Mutex
	config     node.Config
	policyPath string
	roots      *x509.CertPool
	pin        func(int64, string) error
}

func NewAuthority(config node.Config, ca, policy string, pin func(int64, string) error) (*Authority, error) {
	pem, err := SafeFile(ca, false)
	if err != nil {
		return nil, err
	}
	roots := x509.NewCertPool()
	if !roots.AppendCertsFromPEM(pem) {
		return nil, errors.New("NODE-0042: explicit client CA required")
	}
	a := &Authority{config: config, policyPath: policy, roots: roots, pin: pin}
	if pin == nil {
		return nil, errors.New("NODE-0041: durable policy floor required")
	}
	if _, err := a.policy(); err != nil {
		return nil, err
	}
	return a, nil
}
func (a *Authority) policy() (contracts.NodePeerPolicy, error) {
	a.mutex.Lock()
	defer a.mutex.Unlock()
	var policy contracts.NodePeerPolicy
	raw, err := SafeFile(a.policyPath, false)
	if err != nil {
		return policy, err
	}
	if err = wire.Validate("NodePeerPolicy", raw); err != nil {
		return policy, err
	}
	if err = json.Unmarshal(raw, &policy); err != nil {
		return policy, err
	}
	if string(policy.TenantId) != a.config.TenantID || string(policy.NodeId) != a.config.NodeID || policy.RecoveryEpoch != a.config.Epoch {
		return policy, errors.New("NODE-0041: peer policy scope differs")
	}
	hash := sha256.Sum256(raw)
	if err = a.pin(policy.Version, hex.EncodeToString(hash[:])); err != nil {
		return policy, err
	}
	expiry, err := time.Parse(time.RFC3339Nano, string(policy.ExpiresAt))
	now := time.Now()
	if err != nil || !expiry.After(now) || expiry.After(now.Add(7*24*time.Hour)) {
		return policy, errors.New("NODE-0041: peer policy expired or unbounded")
	}
	return policy, nil
}
func hasUsage(cert *x509.Certificate, usage x509.ExtKeyUsage) bool {
	for _, actual := range cert.ExtKeyUsage {
		if actual == usage {
			return true
		}
	}
	return false
}
func (a *Authority) Authorize(state *tls.ConnectionState) error {
	if state == nil || state.Version < tls.VersionTLS13 || len(state.VerifiedChains) == 0 || len(state.PeerCertificates) == 0 {
		return errors.New("NODE-0043: mTLS required")
	}
	policy, err := a.policy()
	if err != nil {
		return err
	}
	cert := state.PeerCertificates[0]
	intermediate := x509.NewCertPool()
	for _, c := range state.PeerCertificates[1:] {
		intermediate.AddCert(c)
	}
	_, err = cert.Verify(x509.VerifyOptions{Roots: a.roots, Intermediates: intermediate, KeyUsages: []x509.ExtKeyUsage{x509.ExtKeyUsageClientAuth}, CurrentTime: time.Now()})
	if err != nil || cert.IsCA || !hasUsage(cert, x509.ExtKeyUsageClientAuth) || len(cert.URIs) != 1 || cert.URIs[0].String() != ControlIdentity(a.config.TenantID, a.config.Epoch) {
		return errors.New("NODE-0043: Control Plane certificate rejected")
	}
	hash := sha256.Sum256(cert.Raw)
	fingerprint := hex.EncodeToString(hash[:])
	for _, allowed := range policy.ClientFingerprints {
		if allowed == fingerprint {
			return nil
		}
	}
	return errors.New("NODE-0043: Control Plane certificate is not enabled")
}
func (a *Authority) TLS(certPath, keyPath string) (*tls.Config, error) {
	get := func(*tls.ClientHelloInfo) (*tls.Certificate, error) {
		certPEM, err := SafeFile(certPath, false)
		if err != nil {
			return nil, err
		}
		keyPEM, err := SafeFile(keyPath, true)
		if err != nil {
			return nil, err
		}
		pair, err := tls.X509KeyPair(certPEM, keyPEM)
		if err != nil || len(pair.Certificate) == 0 {
			return nil, errors.New("NODE-0042: TLS key pair rejected")
		}
		leaf, err := x509.ParseCertificate(pair.Certificate[0])
		now := time.Now()
		if err != nil || leaf.IsCA || !hasUsage(leaf, x509.ExtKeyUsageServerAuth) || len(leaf.URIs) != 1 || leaf.URIs[0].String() != Identity(a.config.TenantID, a.config.NodeID, a.config.Epoch) || now.Before(leaf.NotBefore) || !now.Before(leaf.NotAfter) {
			return nil, errors.New("NODE-0042: Node server identity rejected")
		}
		return &pair, nil
	}
	if _, err := get(nil); err != nil {
		return nil, err
	}
	return &tls.Config{MinVersion: tls.VersionTLS13, ClientAuth: tls.RequireAndVerifyClientCert, ClientCAs: a.roots, GetCertificate: get, SessionTicketsDisabled: true, NextProtos: []string{"http/1.1"}, VerifyConnection: func(s tls.ConnectionState) error { return a.Authorize(&s) }}, nil
}
