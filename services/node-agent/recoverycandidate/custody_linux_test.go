//go:build linux

package recoverycandidate

import (
    "crypto/ed25519"
    "crypto/rand"
    "fmt"
    "os"
    "path/filepath"
    "testing"
)

func TestHistoryRefusesSignedForeignScopeWithSameRetainedKey(t *testing.T) {
    pub,key,err := ed25519.GenerateKey(rand.Reader); if err != nil { t.Fatal(err) }
    root := t.TempDir(); operation := "0123456789abcdef0123456789abcdef"
    requestHash := Hash([]byte("original canonical request")); digest := Hash([]byte("public fixture"))
    proofBody := map[string]any{"schema":"sv-expired-policy-nonserving-proof:1","requestDigest":requestHash,"tenantId":"foreign-tenant","epoch":"epoch","nodeId":"node",
        "assurance":"operator-custody-and-file-lock-not-hardware","serving":false,"servingPID":nil,"operation":operation,"nonce":digest,"counter":1,
        "proposalDigest":digest,"operatorDigest":digest,"helperSHA256":digest,"containerId":digest,"imageId":digest,"lockDevice":1,"lockInode":2,"lockHeldAtSigning":true,
        "observedAt":1,"deadline":100,"priorP":1,"priorC":3,"floorSHA256":digest,"identitySHA256":digest,"configDigest":digest,"previousCheckpoint":"","activationAllowed":false}
    proof,err := Sign(proofBody,ProofDomain,key); if err != nil { t.Fatal(err) }
    proofRaw,_ := Canonical(proof)
    checkpoint,err := Sign(map[string]any{"schema":"sv-expired-policy-candidate-checkpoint:1","counter":1,"operation":operation,"previousCheckpoint":"","requestDigest":requestHash,"proofDigest":Hash(proofRaw),"tenantId":"foreign-tenant","epoch":"epoch","nodeId":"node","ackDigest":digest,"batchProofDigest":digest,"checkpointAt":2,"lockHeldThroughCheckpoint":true,"activationAllowed":false},CheckpointDomain,key); if err != nil { t.Fatal(err) }
    raw,_ := Canonical(map[string]any{"schema":"sv-expired-policy-record:1","requestDigest":requestHash,"proof":proof,"checkpoint":checkpoint})
    if err := os.WriteFile(filepath.Join(root,fmt.Sprintf("%08d-%s.json",1,operation)),raw,0600); err != nil { t.Fatal(err) }
    // Positive control proves signatures/hash/counter/layout are valid.
    _,_,err = ownHistory(root,pub,Binding{Tenant:"foreign-tenant",Epoch:"epoch",Node:"node"})
    if err != nil { t.Fatalf("valid history control failed: %v",err) }
    for _, binding := range []Binding{
        {Tenant:"current-tenant",Epoch:"epoch",Node:"node"},
        {Tenant:"foreign-tenant",Epoch:"other-epoch",Node:"node"},
        {Tenant:"foreign-tenant",Epoch:"epoch",Node:"other-node"},
    } {
        _,_,err = ownHistory(root,pub,binding)
        if ErrorCode(err) != "RECOVERY_HOLD_HISTORY_SCOPE" { t.Fatalf("foreign history was not refused by scope: %v",err) }
    }
}
