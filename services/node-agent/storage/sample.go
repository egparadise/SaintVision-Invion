// Package storage signs bounded observations, never operational health records.
package storage

import (
	"context"
	"crypto/ed25519"
	"crypto/sha256"
	"crypto/tls"
	"crypto/x509"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"net/url"
	"strings"
	"time"

	contracts "github.com/egparadise/SaintVision-Invion/packages/contracts-go"
	"github.com/egparadise/SaintVision-Invion/services/node-agent/internal/wire"
)

const Domain = "saintvision/node-storage-sample/v1\x00"
const MaxBytes int64 = 1024 * 1024

var rejected = errors.New("NODE-0060: storage sample rejected")

type Sampler struct {
	config contracts.NodeStorageRootConfig
	root   *readRoot
}

func Open(raw []byte) (*Sampler, error) {
	if wire.Validate("NodeStorageRootConfig", raw) != nil {
		return nil, rejected
	}
	var config contracts.NodeStorageRootConfig
	if json.Unmarshal(raw, &config) != nil || !endpoint(config.Channel.Endpoint) {
		return nil, rejected
	}
	root, err := openRoot(config.Root)
	if err != nil {
		return nil, rejected
	}
	return &Sampler{config: config, root: root}, nil
}
func (s *Sampler) Close() error { return s.root.close() }

// Validate the current local server key before committing an installation floor.
func (s *Sampler) CheckCertificate(pair *tls.Certificate) error {
	_, err := keyFor(pair, s.config.Channel, time.Now())
	return err
}

func endpoint(value string) bool {
	u, err := url.Parse(value)
	if err != nil || u.Scheme != "https" || u.Hostname() == "" || u.User != nil || (u.Path != "" && u.Path != "/") || u.RawQuery != "" || u.Fragment != "" {
		return false
	}
	for _, c := range value {
		if c < 33 || c > 126 {
			return false
		}
	}
	return true
}

func validPath(path string) bool {
	if strings.ContainsAny(path, "\\:%") {
		return false
	}
	for _, c := range path {
		if c < 32 {
			return false
		}
	}
	for _, part := range strings.Split(path, "/") {
		if part == "" || part == "." || part == ".." {
			return false
		}
	}
	return true
}

func keyFor(pair *tls.Certificate, channel contracts.NodeStorageChannel, now time.Time) (ed25519.PrivateKey, error) {
	if pair == nil || len(pair.Certificate) == 0 {
		return nil, rejected
	}
	cert, err := x509.ParseCertificate(pair.Certificate[0])
	if err != nil {
		return nil, rejected
	}
	sum := sha256.Sum256(cert.Raw)
	identity := "spiffe://saintvision.ai/tenant/" + string(channel.Tenant_id) + "/node/" + string(channel.Node_id) + "/epoch/" + channel.Recovery_epoch
	usage := false
	for _, u := range cert.ExtKeyUsage {
		if u == x509.ExtKeyUsageServerAuth {
			usage = true
		}
	}
	key, ok := pair.PrivateKey.(ed25519.PrivateKey)
	public, pubOK := cert.PublicKey.(ed25519.PublicKey)
	if !ok || !pubOK || !key.Public().(ed25519.PublicKey).Equal(public) || cert.IsCA || !usage || len(cert.URIs) != 1 || cert.URIs[0].String() != identity || now.Before(cert.NotBefore) || !now.Before(cert.NotAfter) || hex.EncodeToString(sum[:]) != channel.Certificate_sha256 {
		return nil, rejected
	}
	return key, nil
}

// Validate and scope the entire request before any contributed file is opened.
// The caller authenticates mTLS, pins local configuration, and supplies the
// current server certificate/key. Request bytes never select a key or root.
func (s *Sampler) Collect(ctx context.Context, raw []byte, pair *tls.Certificate) (map[string]string, error) {
	if s == nil || wire.Validate("NodeStorageSampleInput", raw) != nil {
		return nil, rejected
	}
	var input contracts.NodeStorageSampleInput
	if json.Unmarshal(raw, &input) != nil {
		return nil, rejected
	}
	data, err := base64.StdEncoding.Strict().DecodeString(input.Challenge)
	if err != nil || len(data) > 65536 || base64.StdEncoding.EncodeToString(data) != input.Challenge || wire.Validate("NodeStorageChallenge", data) != nil {
		return nil, rejected
	}
	var challenge contracts.NodeStorageChallenge
	if json.Unmarshal(data, &challenge) != nil {
		return nil, rejected
	}
	started := time.Now()
	if challenge.Channel != s.config.Channel || challenge.Contribution_id != s.config.Contribution_id || challenge.Root_version != s.config.Root_version || challenge.Issued_at > started.Unix() || challenge.Expires_at <= started.Unix() || challenge.Expires_at-challenge.Issued_at > 30 || challenge.Catalogued < int64(len(challenge.Items)) {
		return nil, rejected
	}
	seen := map[string]bool{}
	paths := map[string]bool{}
	for _, item := range challenge.Items {
		if !validPath(item.Relative_path) || seen[item.Location_id] || paths[item.Relative_path] {
			return nil, rejected
		}
		seen[item.Location_id] = true
		paths[item.Relative_path] = true
	}
	key, err := keyFor(pair, challenge.Channel, started)
	if err != nil {
		return nil, rejected
	}
	observations := make([]map[string]any, 0, len(challenge.Items))
	for _, item := range challenge.Items {
		if ctx.Err() != nil || time.Now().Unix() >= challenge.Expires_at {
			return nil, rejected
		}
		row := map[string]any{"locationId": item.Location_id, "sha256": nil, "byteSize": nil}
		if item.Checksum_sha256 != nil {
			sum, size, err := s.root.hash(ctx, item.Relative_path)
			if err == nil {
				row["sha256"] = sum
				row["byteSize"] = size
			}
		}
		observations = append(observations, row)
	}
	finished := time.Now()
	if ctx.Err() != nil || finished.Before(started) || finished.Unix() >= challenge.Expires_at || s.root.current() != nil {
		return nil, rejected
	}
	if _, err = keyFor(pair, challenge.Channel, finished); err != nil {
		return nil, rejected
	}
	sum := sha256.Sum256(append([]byte(Domain), data...))
	// All result strings are fixed ASCII IDs/hashes; encoding/json's sorted map
	// keys therefore produce the same canonical bytes as the Python verifier.
	payload, err := json.Marshal(map[string]any{"protocol": "node-storage-sample-v1", "challengeSha256": hex.EncodeToString(sum[:]), "observedAt": finished.Unix(), "observations": observations})
	if err != nil || len(payload) > 65536 {
		return nil, rejected
	}
	return map[string]string{"payload": base64.StdEncoding.EncodeToString(payload), "signature": base64.StdEncoding.EncodeToString(ed25519.Sign(key, append([]byte(Domain), payload...)))}, nil
}
