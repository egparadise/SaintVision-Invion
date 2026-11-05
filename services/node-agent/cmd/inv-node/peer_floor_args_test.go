package main

import "testing"

func TestPeerFloorArgumentsAreClosedAndUnambiguous(t *testing.T) {
	valid := []string{"--observe-peer-policy-floor", "--tenant", "tenant", "--node", "node", "--epoch", "epoch", "--state", "/state/journal", "--peer-policy", "/state/peer-policy.json", "--tls-cert", "/state/node-cert.pem", "--tls-key", "/state/node-key.pem", "--peer-floor-nonce", "nonce"}
	if !strictPeerFloorArguments(valid) {
		t.Fatal("exact closed command refused")
	}
	for _, extra := range [][]string{{"--node", "other"}, {"--node=other"}, {"-node", "other"}, {"--serve"}, {"--profile", "other"}, {"--peer-floor-serving-pid", "1", "--peer-floor-serving-pid", "2"}} {
		args := append(append([]string{}, valid...), extra...)
		if strictPeerFloorArguments(args) {
			t.Fatalf("ambiguous/unknown command accepted: %v", extra)
		}
	}
	if strictPeerFloorArguments(valid[1:]) || strictPeerFloorArguments(valid[:len(valid)-1]) {
		t.Fatal("missing observation mode/value accepted")
	}
}
