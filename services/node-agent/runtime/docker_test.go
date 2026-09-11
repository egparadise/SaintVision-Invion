package runtime

import (
	"context"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"net"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

func testDocker(t *testing.T, handler http.HandlerFunc) *Docker {
	t.Helper()
	server := httptest.NewServer(handler)
	t.Cleanup(server.Close)
	transport := &http.Transport{Proxy: nil, DialContext: func(ctx context.Context, _, _ string) (net.Conn, error) {
		return (&net.Dialer{}).DialContext(ctx, "tcp", strings.TrimPrefix(server.URL, "http://"))
	}}
	t.Cleanup(transport.CloseIdleConnections)
	return &Docker{client: &http.Client{Transport: transport, Timeout: time.Second}}
}

func TestDockerNegotiationRefusesUnsupportedEngineBeforeMutation(t *testing.T) {
	for _, tc := range []struct{ name, body, version string }{
		{"old-supported", `{"ApiVersion":"1.41","MinAPIVersion":"1.12","Os":"linux"}`, "v1.41"},
		{"newer-supported", `{"ApiVersion":"1.48","MinAPIVersion":"1.24","Os":"linux"}`, "v1.45"},
		{"new-minimum", `{"ApiVersion":"1.52","MinAPIVersion":"1.44","Os":"linux"}`, "v1.45"},
		{"too-old", `{"ApiVersion":"1.40","MinAPIVersion":"1.12","Os":"linux"}`, ""},
		{"too-new-minimum", `{"ApiVersion":"1.52","MinAPIVersion":"1.46","Os":"linux"}`, ""},
		{"windows", `{"ApiVersion":"1.45","MinAPIVersion":"1.24","Os":"windows"}`, ""},
		{"missing-minimum", `{"ApiVersion":"1.45","Os":"linux"}`, ""},
		{"invalid-range", `{"ApiVersion":"1.41","MinAPIVersion":"1.42","Os":"linux"}`, ""},
		{"bad-number", `{"ApiVersion":"1.041","MinAPIVersion":"1.24","Os":"linux"}`, ""},
		{"bad-json", `{`, ""},
		{"trailing-json", `{"ApiVersion":"1.45","MinAPIVersion":"1.24","Os":"linux"} {}`, ""},
	} {
		t.Run(tc.name, func(t *testing.T) {
			mutations := 0
			d := testDocker(t, func(w http.ResponseWriter, r *http.Request) {
				if r.URL.Path == "/version" {
					fmt.Fprint(w, tc.body)
					return
				}
				mutations++
				if r.URL.Path != "/"+tc.version+"/containers/"+strings.Repeat("a", 64)+"/start" {
					t.Error(r.URL.Path)
				}
				w.WriteHeader(204)
			})
			err := d.Start(context.Background(), strings.Repeat("a", 64))
			if (err == nil) != (tc.version != "") || (mutations == 1) != (tc.version != "") {
				t.Fatalf("err=%v mutations=%d", err, mutations)
			}
		})
	}
}

func TestDockerConcurrentNegotiationAndUnavailableRetry(t *testing.T) {
	var versions, mutations atomic.Int32
	d := testDocker(t, func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/version" {
			if versions.Add(1) == 1 {
				w.WriteHeader(503)
				return
			}
			fmt.Fprint(w, `{"ApiVersion":"1.41","MinAPIVersion":"1.12","Os":"linux"}`)
			return
		}
		mutations.Add(1)
		w.WriteHeader(500) // An uncertain mutation must NOT be transparently retried.
	})
	if err := d.Start(context.Background(), strings.Repeat("a", 64)); err == nil || mutations.Load() != 0 {
		t.Fatal("unavailable engine admitted mutation")
	}
	var wg sync.WaitGroup
	for i := 0; i < 8; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			if d.Start(context.Background(), strings.Repeat("a", 64)) == nil {
				t.Error("mutation failure hidden")
			}
		}()
	}
	wg.Wait()
	if versions.Load() != 2 || mutations.Load() != 8 {
		t.Fatalf("versions=%d mutations=%d", versions.Load(), mutations.Load())
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if d.Start(ctx, strings.Repeat("a", 64)) == nil || mutations.Load() != 8 {
		t.Fatal("cancelled request reached engine")
	}
}

func TestDockerOutputUsesNegotiatedVersion(t *testing.T) {
	_, p, _ := fixture(t)
	record := Record{Claim: p.Claim, Name: "negotiated-output"}
	id := strings.Repeat("a", 64)
	d := testDocker(t, func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/version":
			fmt.Fprint(w, `{"ApiVersion":"1.41","MinAPIVersion":"1.12","Os":"linux"}`)
		case "/v1.41/containers/" + id + "/json":
			value := inspection{ID: id, Name: record.Name}
			value.Config.Labels = labels(record)
			value.State.Status = "exited"
			json.NewEncoder(w).Encode(value)
		case "/v1.41/containers/" + id + "/logs":
			data := []byte(`{"stdout":"","stderr":""}`)
			header := make([]byte, 8)
			header[0] = 1
			binary.BigEndian.PutUint32(header[4:], uint32(len(data)))
			w.Write(append(header, data...))
		default:
			t.Error(r.URL.Path)
			w.WriteHeader(404)
		}
	})
	if output, err := d.Output(context.Background(), id, record); err != nil || output.SizeBytes == 0 {
		t.Fatalf("output=%v err=%v", output, err)
	}
}
