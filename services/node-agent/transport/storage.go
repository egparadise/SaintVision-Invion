package transport

import (
	"context"
	"crypto/sha256"
	"crypto/tls"
	"encoding/hex"
	"encoding/json"
	"errors"

	contracts "github.com/egparadise/SaintVision-Invion/packages/contracts-go"
	"github.com/egparadise/SaintVision-Invion/services/node-agent/internal/wire"
	node "github.com/egparadise/SaintVision-Invion/services/node-agent/runtime"
	"github.com/egparadise/SaintVision-Invion/services/node-agent/storage"
)

type StorageSampler interface {
	Sample(context.Context, []byte) (map[string]string, error)
}
type ConfiguredStorage struct {
	path    string
	hash    [32]byte
	sampler *storage.Sampler
	tls     *tls.Config
	receipt node.StoragePolicyPin
}

// One explicitly configured contribution per Node in v1. A changed config
// fails closed until a controlled restart, never silently broadens a live root.
func NewStorageSampler(config node.Config, path string, tlsConfig *tls.Config, pin func(node.StoragePolicyPin) error) (*ConfiguredStorage, error) {
	if pin == nil {
		return nil, errors.New("NODE-0061: durable storage policy floor required")
	}
	raw, err := SafeFile(path, true)
	if err != nil || wire.Validate("NodeStorageRootConfig", raw) != nil {
		return nil, errors.New("NODE-0060: storage configuration unavailable")
	}
	var policy contracts.NodeStorageRootConfig
	if json.Unmarshal(raw, &policy) != nil || string(policy.Channel.Tenant_id) != config.TenantID || string(policy.Channel.Node_id) != config.NodeID || policy.Channel.Recovery_epoch != config.Epoch || tlsConfig == nil || tlsConfig.GetCertificate == nil {
		return nil, errors.New("NODE-0060: storage configuration scope differs")
	}
	sampler, err := storage.Open(raw)
	if err != nil {
		return nil, err
	}
	channel, _ := json.Marshal(policy.Channel)
	digest := func(b []byte) string { h := sha256.Sum256(b); return hex.EncodeToString(h[:]) }
	receipt := node.StoragePolicyPin{ContributionID: policy.Contribution_id, RootVersion: policy.Root_version, ChannelVersion: policy.Channel.Version, RootSHA256: digest([]byte(policy.Root)), ChannelSHA256: digest(channel), PolicySHA256: digest(raw)}
	s := &ConfiguredStorage{path, sha256.Sum256(raw), sampler, tlsConfig, receipt}
	pair, err := tlsConfig.GetCertificate(nil)
	if err == nil {
		err = sampler.CheckCertificate(pair)
	}
	if err == nil && !s.current() {
		err = errors.New("NODE-0060: storage configuration changed")
	}
	if err == nil {
		err = pin(receipt)
	}
	if err != nil {
		_ = sampler.Close()
		return nil, err
	}
	return s, nil
}
func (s *ConfiguredStorage) Installation() node.StoragePolicyPin { return s.receipt }
func (s *ConfiguredStorage) Close() error                        { return s.sampler.Close() }
func (s *ConfiguredStorage) current() bool {
	raw, err := SafeFile(s.path, true)
	return err == nil && sha256.Sum256(raw) == s.hash
}
func (s *ConfiguredStorage) Sample(ctx context.Context, raw []byte) (map[string]string, error) {
	if !s.current() {
		return nil, errors.New("NODE-0060: storage configuration changed")
	}
	pair, err := s.tls.GetCertificate(nil)
	if err != nil {
		return nil, err
	}
	result, err := s.sampler.Collect(ctx, raw, pair)
	if err != nil {
		return nil, err
	}
	current, err := s.tls.GetCertificate(nil)
	if err != nil || len(current.Certificate) == 0 || len(pair.Certificate) == 0 || sha256.Sum256(current.Certificate[0]) != sha256.Sum256(pair.Certificate[0]) || !s.current() || ctx.Err() != nil {
		return nil, errors.New("NODE-0060: storage authority changed")
	}
	return result, nil
}
