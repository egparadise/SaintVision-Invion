package discovery

import (
	"bytes"
	"context"
	"crypto/tls"
	"crypto/x509"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/url"
	"regexp"
	"time"
)

type Announcement struct {
	InstanceID   string            `json:"instanceId"`
	Hostname     string            `json:"hostname"`
	OSType       string            `json:"osType"`
	OSVersion    string            `json:"osVersion"`
	AgentVersion string            `json:"agentVersion"`
	CPUCores     int               `json:"cpuCores"`
	RAMBytes     int64             `json:"ramBytes"`
	GPUCount     int               `json:"gpuCount"`
	Labels       map[string]string `json:"labels"`
}

var tenantID = regexp.MustCompile(`^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$`)

// Announcement grants no admission, certificate, offer, placement or execution.
// TLS server trust is explicit, with no proxy, redirect or automatic retries.
func Send(ctx context.Context, endpoint, tenant string, ca []byte, a Announcement) error {
	u, err := url.Parse(endpoint)
	if err != nil || u.Scheme != "https" || u.Host == "" || u.User != nil || u.Path != "/v1/discovery/announcements" || u.RawPath != "" || u.RawQuery != "" || u.Fragment != "" || !tenantID.MatchString(tenant) {
		return errors.New("discovery configuration rejected")
	}
	if len(a.InstanceID) < 1 || len(a.InstanceID) > 128 || len(a.Hostname) < 1 || len(a.Hostname) > 253 || (a.OSType != "linux" && a.OSType != "windows") || len(a.OSVersion) > 64 || len(a.AgentVersion) > 64 || a.CPUCores < 0 || a.RAMBytes < 0 || a.GPUCount < 0 {
		return errors.New("announcement rejected")
	}
	roots := x509.NewCertPool()
	if !roots.AppendCertsFromPEM(ca) {
		return errors.New("explicit discovery CA required")
	}
	body, err := json.Marshal(a)
	if err != nil || len(body) > 8192 {
		return errors.New("announcement exceeds bound")
	}
	transport := &http.Transport{Proxy: nil, TLSClientConfig: &tls.Config{RootCAs: roots, MinVersion: tls.VersionTLS13}, DisableKeepAlives: true, MaxResponseHeaderBytes: 8192}
	defer transport.CloseIdleConnections()
	client := &http.Client{Transport: transport, Timeout: 5 * time.Second, CheckRedirect: func(*http.Request, []*http.Request) error { return errors.New("redirect refused") }}
	request, err := http.NewRequestWithContext(ctx, "POST", endpoint, bytes.NewReader(body))
	if err != nil {
		return errors.New("discovery request rejected")
	}
	request.Header.Set("Content-Type", "application/json")
	request.Header.Set("X-Inv-Tenant", tenant)
	response, err := client.Do(request)
	if err != nil {
		return errors.New("discovery unavailable")
	}
	defer response.Body.Close()
	raw, err := io.ReadAll(io.LimitReader(response.Body, 8193))
	if err != nil || len(raw) > 8192 || response.StatusCode != 202 {
		return errors.New("announcement not accepted")
	}
	return nil
}
