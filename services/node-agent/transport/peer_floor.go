package transport

import (
	"crypto/ed25519"
	"crypto/sha256"
	"crypto/tls"
	"crypto/x509"
	"encoding/hex"
	"encoding/json"
	"errors"
	"path/filepath"
	"regexp"
	"time"

	node "github.com/egparadise/SaintVision-Invion/services/node-agent/runtime"
)

const PeerFloorDomain = "saintvision/node-peer-policy-floor/v1\x00"

var peerFloorNonce = regexp.MustCompile(`^[0-9a-f]{64}$`)

// Sign an actual existing floor without OpenJournal, pinning, a listener, or
// locking out the serving Node. Missing/incoherent/private state is refused.
func ObservePeerPolicyFloor(config node.Config, state, policy, certPath, keyPath, nonce string, servingPID int) (map[string]any, error) {
	rejected := errors.New("NODE-0041: authenticated actual peer floor unavailable")
	if !peerFloorNonce.MatchString(nonce) || certPath != filepath.Join(filepath.Dir(state), "node-cert.pem") || keyPath != filepath.Join(filepath.Dir(state), "node-key.pem") {
		return nil, rejected
	}
	certRaw, err := SafeFile(certPath, false)
	if err != nil {
		return nil, rejected
	}
	keyRaw, err := SafeFile(keyPath, true)
	if err != nil {
		return nil, rejected
	}
	pair, err := tls.X509KeyPair(certRaw, keyRaw)
	if err != nil || len(pair.Certificate) == 0 {
		return nil, rejected
	}
	cert, err := x509.ParseCertificate(pair.Certificate[0])
	key, ok := pair.PrivateKey.(ed25519.PrivateKey)
	now := time.Now()
	if err != nil || !ok || cert.IsCA || !hasUsage(cert, x509.ExtKeyUsageServerAuth) || len(cert.URIs) != 1 || cert.URIs[0].String() != Identity(config.TenantID, config.NodeID, config.Epoch) || now.Before(cert.NotBefore) || !now.Before(cert.NotAfter) {
		return nil, rejected
	}
	floor, err := node.ReadPeerPolicyFloor(state, policy, config)
	if err != nil {
		return nil, err
	}
	processHash, err := node.PeerFloorServingProcess(servingPID, state, policy, config, floor.JournalUID)
	if err != nil {
		return nil, err
	}
	current, err := SafeFile(certPath, false)
	if err != nil || sha256.Sum256(current) != sha256.Sum256(certRaw) {
		return nil, rejected
	}
	currentKey, err := SafeFile(keyPath, true)
	if err != nil || sha256.Sum256(currentKey) != sha256.Sum256(keyRaw) {
		return nil, rejected
	}
	lastFloor, err := node.ReadPeerPolicyFloor(state, policy, config)
	if err != nil || lastFloor != floor {
		return nil, rejected
	}
	lastProcess, err := node.PeerFloorServingProcess(servingPID, state, policy, config, floor.JournalUID)
	if err != nil || lastProcess != processHash {
		return nil, rejected
	}
	der := sha256.Sum256(cert.Raw)
	body := map[string]any{"schemaVersion": "saintvision-node-peer-policy-floor:1", "tenantId": config.TenantID, "nodeId": config.NodeID, "recoveryEpoch": config.Epoch, "nonce": nonce, "observedAt": now.Unix(), "certificateDER_SHA256": hex.EncodeToString(der[:]), "peerPolicyVersion": floor.Version, "peerPolicySHA256": floor.Hash, "floorSHA256": floor.FloorSHA256, "journalIdentitySHA256": floor.JournalIdentitySHA256, "journalUID": floor.JournalUID, "servingPID": servingPID, "servingProcessSHA256": processHash, "plainServingProcess": true}
	raw, err := json.Marshal(body)
	if err != nil {
		return nil, rejected
	}
	body["nodeSignature"] = hex.EncodeToString(ed25519.Sign(key, append([]byte(PeerFloorDomain), raw...)))
	return body, nil
}
