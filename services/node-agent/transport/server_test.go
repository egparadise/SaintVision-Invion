package transport

import (
	"bytes"
	"context"
	"crypto/ed25519"
	"crypto/rand"
	"crypto/sha256"
	"crypto/tls"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"encoding/pem"
	"errors"
	node "github.com/egparadise/SaintVision-Invion/services/node-agent/runtime"
	"io"
	"log"
	"math/big"
	"net"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

type testCA struct {
	cert *x509.Certificate
	key  ed25519.PrivateKey
	pem  []byte
}

func ca(t *testing.T) testCA {
	t.Helper()
	pub, key, _ := ed25519.GenerateKey(rand.Reader)
	c := &x509.Certificate{SerialNumber: big.NewInt(time.Now().UnixNano()), Subject: pkix.Name{CommonName: "synthetic-ca"}, NotBefore: time.Now().Add(-time.Hour), NotAfter: time.Now().Add(time.Hour), BasicConstraintsValid: true, IsCA: true, KeyUsage: x509.KeyUsageCertSign}
	raw, err := x509.CreateCertificate(rand.Reader, c, c, pub, key)
	if err != nil {
		t.Fatal(err)
	}
	parsed, _ := x509.ParseCertificate(raw)
	return testCA{parsed, key, pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: raw})}
}
func issue(t *testing.T, ca testCA, identity string, usage x509.ExtKeyUsage, expired bool) (tls.Certificate, []byte, []byte, string) {
	t.Helper()
	pub, key, _ := ed25519.GenerateKey(rand.Reader)
	uri, _ := url.Parse(identity)
	expiry := time.Now().Add(time.Hour)
	if expired {
		expiry = time.Now().Add(-time.Minute)
	}
	c := &x509.Certificate{SerialNumber: big.NewInt(time.Now().UnixNano()), Subject: pkix.Name{CommonName: "synthetic-peer"}, NotBefore: time.Now().Add(-time.Hour), NotAfter: expiry, BasicConstraintsValid: true, KeyUsage: x509.KeyUsageDigitalSignature, ExtKeyUsage: []x509.ExtKeyUsage{usage}, URIs: []*url.URL{uri}, IPAddresses: []net.IP{net.ParseIP("127.0.0.1")}}
	raw, err := x509.CreateCertificate(rand.Reader, c, ca.cert, pub, ca.key)
	if err != nil {
		t.Fatal(err)
	}
	private, _ := x509.MarshalPKCS8PrivateKey(key)
	cp := pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: raw})
	kp := pem.EncodeToMemory(&pem.Block{Type: "PRIVATE KEY", Bytes: private})
	pair, err := tls.X509KeyPair(cp, kp)
	if err != nil {
		t.Fatal(err)
	}
	hash := sha256.Sum256(raw)
	return pair, cp, kp, hex.EncodeToString(hash[:])
}

type fakeRunner struct {
	calls   atomic.Int32
	wait    atomic.Bool
	started chan struct{}
}

func (f *fakeRunner) Execute(ctx context.Context, _ []byte) (node.Result, error) {
	f.calls.Add(1)
	if f.wait.Load() {
		close(f.started)
		<-ctx.Done()
	}
	return node.Result{}, errors.New("synthetic executor")
}
func (f *fakeRunner) Observe(ctx context.Context, raw []byte) (node.Result, error) {
	return f.Execute(ctx, raw)
}
func write(t *testing.T, path string, data []byte) {
	t.Helper()
	temporary, err := os.CreateTemp(filepath.Dir(path), ".policy-")
	if err != nil {
		t.Fatal(err)
	}
	if _, err = temporary.Write(data); err != nil {
		t.Fatal(err)
	}
	_ = temporary.Close()
	if err = os.Rename(temporary.Name(), path); err != nil {
		t.Fatal(err)
	}
}

type setup struct {
	c           node.Config
	ca          testCA
	authority   *Authority
	policy      string
	cert        tls.Certificate
	fingerprint string
	server      *httptest.Server
	runner      *fakeRunner
	client      *http.Client
	handshakes  atomic.Int32
}

func (s *setup) policyAt(t *testing.T, version int64, pins []string, expiry time.Time) {
	raw, _ := json.Marshal(map[string]any{"version": version, "tenantId": s.c.TenantID, "nodeId": s.c.NodeID, "recoveryEpoch": s.c.Epoch, "expiresAt": expiry.UTC().Format(time.RFC3339Nano), "clientFingerprints": pins})
	write(t, s.policy, raw)
}
func (s *setup) newClient(cert *tls.Certificate) *http.Client {
	roots := x509.NewCertPool()
	roots.AppendCertsFromPEM(s.ca.pem)
	config := &tls.Config{RootCAs: roots, MinVersion: tls.VersionTLS13}
	if cert != nil {
		config.Certificates = []tls.Certificate{*cert}
	}
	return &http.Client{Transport: &http.Transport{TLSClientConfig: config, Proxy: nil}, Timeout: 4 * time.Second}
}
func fixture(t *testing.T) *setup {
	t.Helper()
	s := &setup{c: node.Config{TenantID: "11111111-1111-4111-8111-111111111111", NodeID: "nod_00000000000000000000000000", Epoch: "22222222-2222-4222-8222-222222222222"}, ca: ca(t), runner: &fakeRunner{started: make(chan struct{})}}
	dir := t.TempDir()
	s.policy = filepath.Join(dir, "policy.json")
	s.cert, _, _, s.fingerprint = issue(t, s.ca, ControlIdentity(s.c.TenantID, s.c.Epoch), x509.ExtKeyUsageClientAuth, false)
	s.policyAt(t, 1, []string{s.fingerprint}, time.Now().Add(time.Hour))
	_, cert, key, _ := issue(t, s.ca, Identity(s.c.TenantID, s.c.NodeID, s.c.Epoch), x509.ExtKeyUsageServerAuth, false)
	caPath := filepath.Join(dir, "ca.pem")
	certPath := filepath.Join(dir, "cert.pem")
	keyPath := filepath.Join(dir, "key.pem")
	write(t, caPath, s.ca.pem)
	write(t, certPath, cert)
	write(t, keyPath, key)
	var mutex sync.Mutex
	var floor int64
	var digest string
	pin := func(version int64, hash string) error {
		mutex.Lock()
		defer mutex.Unlock()
		if version < floor || (version == floor && hash != digest) {
			return errors.New("rollback")
		}
		floor = version
		digest = hash
		return nil
	}
	a, err := NewAuthority(s.c, caPath, s.policy, pin)
	if err != nil {
		t.Fatal(err)
	}
	s.authority = a
	tc, err := a.TLS(certPath, keyPath)
	if err != nil {
		t.Fatal(err)
	}
	verify := tc.VerifyConnection
	tc.VerifyConnection = func(c tls.ConnectionState) error { s.handshakes.Add(1); return verify(c) }
	server := httptest.NewUnstartedServer(Handler(a, s.runner))
	server.Config.ErrorLog = log.New(io.Discard, "", 0)
	server.TLS = tc
	pair, err := tc.GetCertificate(nil)
	if err != nil {
		t.Fatal(err)
	}
	server.TLS.Certificates = []tls.Certificate{*pair}
	server.StartTLS()
	s.server = server
	s.client = s.newClient(&s.cert)
	t.Cleanup(server.Close)
	t.Cleanup(s.client.CloseIdleConnections)
	return s
}
func envelope() []byte {
	raw, _ := json.Marshal(map[string]string{"payload": "e30=", "signature": base64.StdEncoding.EncodeToString(make([]byte, 64))})
	return raw
}
func call(t *testing.T, client *http.Client, address, path string, body []byte) (int, error) {
	t.Helper()
	req, _ := http.NewRequest("POST", address+path, bytes.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	response, err := client.Do(req)
	if err != nil {
		return 0, err
	}
	defer response.Body.Close()
	_, _ = io.Copy(io.Discard, response.Body)
	return response.StatusCode, nil
}
func TestMTLSAllowsOnlyPinnedScopedClient(t *testing.T) {
	s := fixture(t)
	status, err := call(t, s.client, s.server.URL, "/v1/executions", envelope())
	if err != nil || status != 503 || s.runner.calls.Load() != 1 {
		t.Fatal("authenticated call did not reach executor", status, err)
	}
	for _, kind := range []string{"no-certificate", "wrong-ca", "wrong-uri", "expired", "wrong-eku", "unpinned"} {
		t.Run(kind, func(t *testing.T) {
			signer := s.ca
			identity := ControlIdentity(s.c.TenantID, s.c.Epoch)
			usage := x509.ExtKeyUsageClientAuth
			if kind == "wrong-ca" {
				signer = ca(t)
			}
			if kind == "wrong-uri" {
				identity += "/forged"
			}
			if kind == "wrong-eku" {
				usage = x509.ExtKeyUsageServerAuth
			}
			cert, _, _, fingerprint := issue(t, signer, identity, usage, kind == "expired")
			if kind != "unpinned" {
				s.policyAt(t, 2+int64(s.handshakes.Load()), []string{fingerprint}, time.Now().Add(time.Hour))
			}
			var selected *tls.Certificate = &cert
			if kind == "no-certificate" {
				selected = nil
			}
			client := s.newClient(selected)
			defer client.CloseIdleConnections()
			before := s.runner.calls.Load()
			status, err := call(t, client, s.server.URL, "/v1/executions", envelope())
			if err == nil && status != 403 {
				t.Fatal("invalid peer admitted", status)
			}
			if s.runner.calls.Load() != before {
				t.Fatal("invalid identity reached runner")
			}
		})
	}
}
func TestPolicyRevocationOnExistingTLSConnection(t *testing.T) {
	s := fixture(t)
	_, err := call(t, s.client, s.server.URL, "/v1/executions", envelope())
	if err != nil {
		t.Fatal(err)
	}
	before := s.handshakes.Load()
	s.policyAt(t, 2, []string{}, time.Now().Add(time.Hour))
	status, err := call(t, s.client, s.server.URL, "/v1/executions", envelope())
	if err != nil || status != 403 || s.runner.calls.Load() != 1 || s.handshakes.Load() != before {
		t.Fatal("existing connection bypassed revocation", status, err)
	}
}
func TestClientCertificateOverlapAndRollback(t *testing.T) {
	s := fixture(t)
	next, _, _, fingerprint := issue(t, s.ca, ControlIdentity(s.c.TenantID, s.c.Epoch), x509.ExtKeyUsageClientAuth, false)
	client := s.newClient(&next)
	defer client.CloseIdleConnections()
	s.policyAt(t, 2, []string{s.fingerprint, fingerprint}, time.Now().Add(time.Hour))
	if status, err := call(t, client, s.server.URL, "/v1/executions", envelope()); err != nil || status != 503 {
		t.Fatal("rotation overlap rejected", err)
	}
	s.policyAt(t, 3, []string{fingerprint}, time.Now().Add(time.Hour))
	if status, err := call(t, client, s.server.URL, "/v1/executions", envelope()); err != nil || status != 503 {
		t.Fatal("new certificate rejected", err)
	}
	s.policyAt(t, 2, []string{s.fingerprint}, time.Now().Add(time.Hour))
	if status, err := call(t, client, s.server.URL, "/v1/executions", envelope()); err == nil && status != 403 {
		t.Fatal("policy rollback admitted")
	}
}
func TestRevocationCancelsActiveRequest(t *testing.T) {
	s := fixture(t)
	s.runner.wait.Store(true)
	done := make(chan struct{})
	go func() { defer close(done); _, _ = call(t, s.client, s.server.URL, "/v1/executions", envelope()) }()
	select {
	case <-s.runner.started:
	case <-time.After(3 * time.Second):
		t.Fatal("not started")
	}
	s.policyAt(t, 2, []string{}, time.Now().Add(time.Hour))
	select {
	case <-done:
	case <-time.After(3 * time.Second):
		t.Fatal("revoked request continued")
	}
}
func TestInvalidPolicyAndFramingNeverReachExecutor(t *testing.T) {
	for _, kind := range []string{"expired-policy", "same-version-change", "malformed-policy", "oversize-body", "query", "wrong-path"} {
		t.Run(kind, func(t *testing.T) {
			s := fixture(t)
			body := envelope()
			path := "/v1/executions"
			switch kind {
			case "expired-policy":
				s.policyAt(t, 2, []string{s.fingerprint}, time.Now().Add(-time.Second))
			case "same-version-change":
				s.policyAt(t, 1, []string{}, time.Now().Add(time.Hour))
			case "malformed-policy":
				write(t, s.policy, []byte("{"))
			case "oversize-body":
				body = bytes.Repeat([]byte("x"), 2*1024*1024+1)
			case "query":
				path += "?identity=trusted"
			case "wrong-path":
				path = "/admin"
			}
			status, err := call(t, s.client, s.server.URL, path, body)
			if err == nil && status == 200 {
				t.Fatal("invalid request accepted")
			}
			if s.runner.calls.Load() != 0 {
				t.Fatal("invalid request reached executor")
			}
		})
	}
}
func TestPlainHTTPIdentityHeadersHaveNoAuthority(t *testing.T) {
	s := fixture(t)
	request := httptest.NewRequest("POST", "http://local/v1/executions", bytes.NewReader(envelope()))
	request.Header.Set("X-Node-Id", s.c.NodeID)
	request.Header.Set("X-SSL-Client-Verify", "SUCCESS")
	request.Header.Set("Content-Type", "application/json")
	response := httptest.NewRecorder()
	Handler(s.authority, s.runner).ServeHTTP(response, request)
	if response.Code != 403 || s.runner.calls.Load() != 0 {
		t.Fatal("forged header accepted")
	}
}

type heldResponse struct {
	*httptest.ResponseRecorder
	entered chan struct{}
	release chan struct{}
}

func (w *heldResponse) WriteHeader(status int) {
	close(w.entered)
	<-w.release
	w.ResponseRecorder.WriteHeader(status)
}

func TestReceiptObservationWaitsForPriorHTTPResponseSlot(t *testing.T) {
	s := fixture(t)
	leaf, err := x509.ParseCertificate(s.cert.Certificate[0])
	if err != nil {
		t.Fatal(err)
	}
	request := func(path string) *http.Request {
		r := httptest.NewRequest("POST", "https://local"+path, bytes.NewReader(envelope()))
		r.Header.Set("Content-Type", "application/json")
		r.TLS = &tls.ConnectionState{Version: tls.VersionTLS13, PeerCertificates: []*x509.Certificate{leaf}, VerifiedChains: [][]*x509.Certificate{{leaf, s.ca.cert}}}
		return r
	}
	h := Handler(s.authority, s.runner)
	w := &heldResponse{ResponseRecorder: httptest.NewRecorder(), entered: make(chan struct{}), release: make(chan struct{})}
	done := make(chan struct{})
	go func() { defer close(done); h.ServeHTTP(w, request("/v1/executions")) }()
	released := false
	defer func() {
		if !released {
			close(w.release)
		}
		<-done
	}()
	select {
	case <-w.entered:
	case <-time.After(3 * time.Second):
		t.Fatal("execution did not reach response")
	}
	// The executor has returned, but its HTTP response still owns the slot.
	busy := httptest.NewRecorder()
	h.ServeHTTP(busy, request("/v1/executions/receipts"))
	if busy.Code != 429 || s.runner.calls.Load() != 1 {
		t.Fatal("observation bypassed bounded execution slot", busy.Code)
	}
	close(w.release)
	released = true
	<-done
	again := httptest.NewRecorder()
	h.ServeHTTP(again, request("/v1/executions/receipts"))
	// This fake returns an error and cannot attest a real receipt. The second
	// request reaches Observe only after the response slot is available.
	if again.Code != 503 || s.runner.calls.Load() != 2 {
		t.Fatal("observation did not reach runner after response completed", again.Code)
	}
}
