package discovery

import (
	"context"
	"crypto/tls"
	"encoding/json"
	"encoding/pem"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestAnnouncementUsesExplicitTLSAndClaudeWireFields(t *testing.T) {
	var received Announcement
	server := httptest.NewUnstartedServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "POST" || r.URL.Path != "/v1/discovery/announcements" || r.Header.Get("X-Inv-Tenant") != "00000000-0000-0000-0000-000000000001" || r.Header.Get("Authorization") != "" {
			t.Error("unexpected discovery authority")
		}
		if err := json.NewDecoder(r.Body).Decode(&received); err != nil {
			t.Error(err)
		}
		w.WriteHeader(202)
	}))
	server.TLS = &tls.Config{MinVersion: tls.VersionTLS13}
	server.StartTLS()
	defer server.Close()
	ca := pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: server.Certificate().Raw})
	a := Announcement{InstanceID: "fixture-installation", Hostname: "synthetic-host", OSType: "linux", OSVersion: "synthetic", AgentVersion: "0.1.0", CPUCores: 2, Labels: map[string]string{}}
	if err := Send(context.Background(), server.URL+"/v1/discovery/announcements", "00000000-0000-0000-0000-000000000001", ca, a); err != nil {
		t.Fatal(err)
	}
	if received.InstanceID != a.InstanceID || received.CPUCores != 2 {
		t.Fatal("wire mapping differs")
	}
	if err := Send(context.Background(), server.URL+"/v1/discovery/announcements", "00000000-0000-0000-0000-000000000001", []byte("untrusted"), a); err == nil {
		t.Fatal("untrusted CA accepted")
	}
}
func TestAnnouncementRefusesRedirects(t *testing.T) {
	count := 0
	server := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { count++; http.Redirect(w, r, "/elsewhere", 307) }))
	defer server.Close()
	ca := pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: server.Certificate().Raw})
	err := Send(context.Background(), server.URL+"/v1/discovery/announcements", "00000000-0000-0000-0000-000000000001", ca, Announcement{InstanceID: "id", Hostname: "host", OSType: "linux"})
	if err == nil || count != 1 {
		t.Fatal("redirect followed")
	}
}
