// inv-recovery-custody is a non-serving PROPOSED candidate. It never opens a
// listener, changes peer policy/floors, provisions a channel or enables admission.
package main

import (
	"encoding/json"
	"flag"
	"io"
	"os"

	proof "github.com/egparadise/SaintVision-Invion/services/node-agent/recoverycandidate"
)

func run() error {
	fs := flag.NewFlagSet("candidate-custody", flag.ContinueOnError)
	fs.SetOutput(io.Discard)
	var b proof.Binding
	var candidate bool
	var request string
	fs.BoolVar(&candidate, "candidate-custody-proof-only", false, "explicit non-serving candidate only")
	fs.StringVar(&request, "request", "", "public signed request under /trust")
	fs.StringVar(&b.Node, "node", "", "out-of-band Node binding")
	fs.StringVar(&b.Tenant, "tenant", "", "out-of-band tenant binding")
	fs.StringVar(&b.Epoch, "epoch", "", "out-of-band epoch binding")
	fs.StringVar(&b.MembersDigest, "members-digest", "", "out-of-band exact cohort binding")
	fs.StringVar(&b.AuthorizerHash, "authorizer-sha256", "", "public recovery-role key pin")
	fs.StringVar(&b.OperatorHash, "operator-sha256", "", "distinct public operator-role key pin")
	fs.StringVar(&b.HelperHash, "helper-sha256", "", "reviewed helper executable pin")
	seen := map[string]bool{}
	for i := 1; i < len(os.Args); i++ {
		name := os.Args[i]
		if name != "--candidate-custody-proof-only" && name != "--request" && name != "--node" && name != "--tenant" && name != "--epoch" && name != "--members-digest" && name != "--authorizer-sha256" && name != "--operator-sha256" && name != "--helper-sha256" { return proof.Refusal("RECOVERY_HOLD_ARGUMENTS") }
		if seen[name] { return proof.Refusal("RECOVERY_HOLD_ARGUMENTS") }
		seen[name] = true
		if name != "--candidate-custody-proof-only" { i++ }
	}
	if fs.Parse(os.Args[1:]) != nil || !candidate || fs.NArg() != 0 || len(seen) != 9 || request != "/trust/request.json" { return proof.Refusal("RECOVERY_HOLD_UNBOUND") }
	raw, err := proof.ReadRequest(request); if err != nil { return err }
	b.ConfigRoot, b.StateRoot, b.CustodyRoot, b.TrustRoot = "/config", "/state", "/custody", "/trust"
	return proof.Run(raw,b,os.Stdin,os.Stdout)
}

func main() {
	if err := run(); err != nil {
		_ = json.NewEncoder(os.Stdout).Encode(map[string]any{"error":proof.ErrorCode(err),"activationAllowed":false})
		os.Exit(1)
	}
}
