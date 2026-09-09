package transport

import (
	"context"
	"crypto/tls"
	"encoding/json"
	"errors"
	"github.com/egparadise/SaintVision-Invion/services/node-agent/internal/wire"
	node "github.com/egparadise/SaintVision-Invion/services/node-agent/runtime"
	"io"
	"log"
	"net"
	"net/http"
	"sync"
	"time"
)

type Executor interface {
	Execute(context.Context, []byte) (node.Result, error)
	Observe(context.Context, []byte) (node.Result, error)
}
type handler struct {
	authority   *Authority
	runner      Executor
	slot        chan struct{}
	controlSlot chan struct{}
}

func Handler(authority *Authority, runner Executor) http.Handler {
	return &handler{authority: authority, runner: runner, slot: make(chan struct{}, 1), controlSlot: make(chan struct{}, 1)}
}
func reject(w http.ResponseWriter, status int) {
	w.Header().Set("Content-Type", "application/problem+json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(map[string]any{"type": "about:blank", "title": "Node request rejected", "status": status, "code": "NODE-0040", "retryable": false})
}
func (h *handler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if h.authority.Authorize(r.TLS) != nil {
		reject(w, 403)
		return
	}
	probe := r.URL.Path == "/v1/heartbeats"
	cancelling := r.URL.Path == "/v1/executions/cancel"
	if r.Method != "POST" || (r.URL.Path != "/v1/executions" && r.URL.Path != "/v1/executions/receipts" && !probe && !cancelling) || r.URL.RawQuery != "" || r.URL.RawPath != "" {
		reject(w, 404)
		return
	}
	if r.Header.Get("Content-Type") != "application/json" || r.Header.Get("Content-Encoding") != "" {
		reject(w, 415)
		return
	}
	slot := h.slot
	if probe || cancelling {
		slot = h.controlSlot
	}
	select {
	case slot <- struct{}{}:
		defer func() { <-slot }()
	default:
		reject(w, 429)
		return
	}
	raw, err := io.ReadAll(io.LimitReader(r.Body, 2*1024*1024+1))
	contract := "SignedNodePermit"
	if probe {
		contract = "NodeProbeInput"
	}
	if err != nil || len(raw) > 2*1024*1024 || wire.Validate(contract, raw) != nil {
		reject(w, 400)
		return
	}
	// Revalidate after potentially slow request-body delivery, then monitor live
	// authority while execution runs. Revocation cancels work on existing TLS too.
	if h.authority.Authorize(r.TLS) != nil {
		reject(w, 403)
		return
	}
	if probe {
		var input struct {
			Nonce string `json:"nonce"`
		}
		_ = json.Unmarshal(raw, &input)
		config := h.authority.config
		body, _ := json.Marshal(map[string]any{"nonce": input.Nonce, "tenantId": config.TenantID, "nodeId": config.NodeID, "recoveryEpoch": config.Epoch, "profileVersion": config.Profile, "observedAt": time.Now().UTC().Format(time.RFC3339Nano)})
		if wire.Validate("NodeProbeResult", body) != nil {
			reject(w, 503)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("Cache-Control", "no-store")
		_, _ = w.Write(body)
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 35*time.Second)
	defer cancel()
	monitorDone := make(chan struct{})
	defer close(monitorDone)
	go func() {
		ticker := time.NewTicker(100 * time.Millisecond)
		defer ticker.Stop()
		for {
			select {
			case <-monitorDone:
				return
			case <-ctx.Done():
				return
			case <-ticker.C:
				if h.authority.Authorize(r.TLS) != nil {
					cancel()
					return
				}
			}
		}
	}()
	var result node.Result
	if cancelling {
		stopper, ok := h.runner.(interface {
			Cancel(context.Context, []byte) (node.Result, error)
		})
		if !ok {
			reject(w, 503)
			return
		}
		result, err = stopper.Cancel(ctx, raw)
	} else if r.URL.Path == "/v1/executions/receipts" {
		result, err = h.runner.Observe(ctx, raw)
	} else {
		result, err = h.runner.Execute(ctx, raw)
	}
	if err != nil {
		reject(w, 503)
		return
	}
	if h.authority.Authorize(r.TLS) != nil {
		reject(w, 403)
		return
	}
	body, err := json.Marshal(result)
	if err != nil || len(body) > 1048576 || wire.Validate("NodeExecutionResult", body) != nil {
		reject(w, 503)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Cache-Control", "no-store")
	w.WriteHeader(200)
	_, _ = w.Write(body)
}

// Limits simultaneous TLS handshakes/connections; authenticated execution is serial.
type limitedListener struct {
	net.Listener
	slots chan struct{}
}
type limitedConn struct {
	net.Conn
	once    sync.Once
	release func()
}

func (c *limitedConn) Close() error { err := c.Conn.Close(); c.once.Do(c.release); return err }
func (l *limitedListener) Accept() (net.Conn, error) {
	for {
		c, err := l.Listener.Accept()
		if err != nil {
			return nil, err
		}
		select {
		case l.slots <- struct{}{}:
			return &limitedConn{Conn: c, release: func() { <-l.slots }}, nil
		default:
			_ = c.Close()
		}
	}
}
func Serve(ctx context.Context, listener net.Listener, config *tls.Config, handler http.Handler) error {
	bounded := &limitedListener{Listener: listener, slots: make(chan struct{}, 16)}
	server := &http.Server{Handler: handler, TLSConfig: config, ReadHeaderTimeout: 3 * time.Second, ReadTimeout: 5 * time.Second, WriteTimeout: 40 * time.Second, IdleTimeout: 5 * time.Second, MaxHeaderBytes: 8192, ErrorLog: log.New(io.Discard, "", 0), BaseContext: func(net.Listener) context.Context { return ctx }}
	stopped := make(chan struct{})
	defer close(stopped)
	shutdownDone := make(chan struct{})
	go func() {
		defer close(shutdownDone)
		select {
		case <-stopped:
			return
		case <-ctx.Done():
			shutdown, cancel := context.WithTimeout(context.Background(), 8*time.Second)
			defer cancel()
			_ = server.Shutdown(shutdown)
		}
	}()
	err := server.Serve(tls.NewListener(bounded, config))
	if errors.Is(err, http.ErrServerClosed) {
		<-shutdownDone
		return nil
	}
	return err
}
