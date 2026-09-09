package main

import (
	"context"
	"crypto/ed25519"
	"encoding/json"
	"flag"
	"fmt"
	node "github.com/egparadise/SaintVision-Invion/services/node-agent/runtime"
	transport "github.com/egparadise/SaintVision-Invion/services/node-agent/transport"
	"io"
	"net"
	"os"
	"os/signal"
	"syscall"
	"time"
)

func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
func run() error {
	var config node.Config
	var state, socket, key, permit string
	var recoverOnly, serve bool
	var listen, tlsCert, tlsKey, clientCA, peerPolicy string
	flag.StringVar(&config.TenantID, "tenant", "", "verified tenant")
	flag.StringVar(&config.NodeID, "node", "", "registered Node")
	flag.StringVar(&config.Epoch, "epoch", "", "operator-provisioned epoch")
	flag.StringVar(&config.Profile, "profile", "", "local allowed profile")
	flag.StringVar(&config.Image, "image", "", "local allowed image content digest")
	flag.StringVar(&config.Executable, "executable", "", "allowed container executable")
	flag.StringVar(&state, "state", "", "private durable journal directory")
	flag.StringVar(&key, "public-key", "", "pinned Ed25519 public key file")
	flag.StringVar(&permit, "permit", "", "signed permit JSON file")
	flag.StringVar(&socket, "socket", "/var/run/docker.sock", "local Docker Unix socket")
	flag.BoolVar(&recoverOnly, "recover", false, "reconcile owned pending executions without restarting")
	flag.BoolVar(&serve, "serve", false, "serve the authenticated Node execution endpoint")
	flag.StringVar(&listen, "listen", "127.0.0.1:8443", "explicit Node listen address")
	flag.StringVar(&tlsCert, "tls-cert", "", "Node server certificate chain PEM")
	flag.StringVar(&tlsKey, "tls-key", "", "private Node TLS key PEM")
	flag.StringVar(&clientCA, "client-ca", "", "explicit Control Plane client CA PEM")
	flag.StringVar(&peerPolicy, "peer-policy", "", "versioned local Control Plane allowlist JSON")
	flag.Parse()
	if serve && (recoverOnly || permit != "") {
		return fmt.Errorf("NODE-0005: choose one execution mode")
	}
	config.MaxCPU = 1000
	config.MaxMemory = 512 * 1024 * 1024
	config.MaxTimeout = 30 * time.Second
	if state == "" || config.NodeID == "" || config.TenantID == "" || config.Epoch == "" || config.Profile == "" || config.Image == "" || config.Executable == "" {
		return fmt.Errorf("NODE-0005: explicit local configuration required")
	}
	public, err := transport.SafeFile(key, false)
	if err != nil || len(public) != ed25519.PublicKeySize {
		return fmt.Errorf("NODE-0005: pinned public key unavailable")
	}
	config.PublicKey = ed25519.PublicKey(public)
	journal, err := node.OpenJournal(state, config)
	if err != nil {
		return err
	}
	defer journal.Close()
	engine, err := node.NewDocker(socket)
	if err != nil {
		return err
	}
	runner := node.New(config, journal, engine)
	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer cancel()
	if serve {
		authority, err := transport.NewAuthority(config, clientCA, peerPolicy, journal.PinPeerPolicy)
		if err != nil {
			return err
		}
		tlsConfig, err := authority.TLS(tlsCert, tlsKey)
		if err != nil {
			return err
		}
		listener, err := net.Listen("tcp", listen)
		if err != nil {
			return fmt.Errorf("NODE-0042: Node listen failed")
		}
		defer listener.Close()
		// Fixed-format local startup record contains no credential or request data.
		if err = json.NewEncoder(os.Stdout).Encode(map[string]string{"listening": listener.Addr().String()}); err != nil {
			return err
		}
		return transport.Serve(ctx, listener, tlsConfig, transport.Handler(authority, runner))
	}
	if recoverOnly {
		results, err := runner.Recover(ctx)
		if err != nil {
			return err
		}
		return json.NewEncoder(os.Stdout).Encode(results)
	}
	file, err := os.Open(permit)
	if err != nil {
		return fmt.Errorf("NODE-0003: permit unavailable")
	}
	defer file.Close()
	raw, err := io.ReadAll(io.LimitReader(file, 2*1024*1024+1))
	if err != nil {
		return fmt.Errorf("NODE-0003: permit unreadable")
	}
	result, err := runner.Execute(ctx, raw)
	if err != nil {
		return err
	}
	return json.NewEncoder(os.Stdout).Encode(result)
}
