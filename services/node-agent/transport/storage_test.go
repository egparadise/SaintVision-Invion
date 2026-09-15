package transport

import (
	"context"
	"encoding/base64"
	"net/http"
	"strings"
	"testing"
	"time"
)

type sampleFunc func(context.Context, []byte) (map[string]string, error)

func (f sampleFunc) Sample(c context.Context, b []byte) (map[string]string, error) { return f(c, b) }
func signedPlaceholder() map[string]string {
	return map[string]string{"payload": "e30=", "signature": base64.StdEncoding.EncodeToString(make([]byte, 64))}
}

func TestStorageDisabledWithoutLocalConfiguration(t *testing.T) {
	s := fixture(t)
	status, err := call(t, s.client, s.server.URL, "/v1/storage/sample", []byte(`{"challenge":"e30="}`))
	if err != nil || status != 503 {
		t.Fatalf("status=%d err=%v", status, err)
	}
}
func TestStorageRechecksPeerAfterCollection(t *testing.T) {
	s := fixture(t)
	h := s.server.Config.Handler.(*handler)
	h.authority.config.Profile = "storage-test-v1"
	h.storageSlot = make(chan struct{}, 1)
	h.storage = sampleFunc(func(context.Context, []byte) (map[string]string, error) {
		s.policyAt(t, 2, []string{}, time.Now().Add(time.Hour))
		return signedPlaceholder(), nil
	})
	status, err := call(t, s.client, s.server.URL, "/v1/storage/sample", []byte(`{"challenge":"e30="}`))
	if err != nil || status != 403 {
		t.Fatalf("revocation status=%d err=%v", status, err)
	}
}
func TestStorageSlotDoesNotConsumeHeartbeatCapacity(t *testing.T) {
	s := fixture(t)
	h := s.server.Config.Handler.(*handler)
	h.authority.config.Profile = "storage-test-v1"
	h.storageSlot = make(chan struct{}, 1)
	started := make(chan struct{})
	release := make(chan struct{})
	h.storage = sampleFunc(func(ctx context.Context, _ []byte) (map[string]string, error) {
		close(started)
		select {
		case <-release:
		case <-ctx.Done():
			return nil, ctx.Err()
		}
		return signedPlaceholder(), nil
	})
	done := make(chan int, 1)
	go func() {
		request, _ := http.NewRequest("POST", s.server.URL+"/v1/storage/sample", strings.NewReader(`{"challenge":"e30="}`))
		request.Header.Set("Content-Type", "application/json")
		response, err := s.client.Do(request)
		if err != nil {
			done <- 0
			return
		}
		defer response.Body.Close()
		done <- response.StatusCode
	}()
	select {
	case <-started:
	case <-time.After(3 * time.Second):
		t.Fatal("sample not started")
	}
	status, err := call(t, s.client, s.server.URL, "/v1/storage/sample", []byte(`{"challenge":"e30="}`))
	if err != nil || status != 429 {
		t.Errorf("concurrency status=%d err=%v", status, err)
	}
	status, err = call(t, s.client, s.server.URL, "/v1/heartbeats", []byte(`{"nonce":"`+strings.Repeat("a", 64)+`"}`))
	if err != nil || status != 200 {
		t.Errorf("heartbeat status=%d err=%v", status, err)
	}
	close(release)
	if <-done != 200 {
		t.Fatal("first sample failed")
	}
}
