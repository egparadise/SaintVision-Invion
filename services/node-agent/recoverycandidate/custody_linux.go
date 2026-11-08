//go:build linux

package recoverycandidate

import (
	"bufio"
	"bytes"
	"crypto/ed25519"
	"crypto/x509"
	"encoding/base64"
	"encoding/pem"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"syscall"
	"time"
)

type Binding struct {
	Node, Tenant, Epoch, MembersDigest, AuthorizerHash, OperatorHash, HelperHash string
	ConfigRoot, StateRoot, CustodyRoot, TrustRoot string
}

func readRegular(path string, empty bool) ([]byte, *syscall.Stat_t, error) {
	fd, err := syscall.Open(path, syscall.O_RDONLY|syscall.O_NOFOLLOW|syscall.O_NONBLOCK, 0)
	if err != nil { return nil, nil, refuse("RECOVERY_HOLD_FILE") }
	f := os.NewFile(uintptr(fd), path); defer f.Close()
	var before, after syscall.Stat_t
	if syscall.Fstat(fd, &before) != nil || before.Mode&syscall.S_IFMT != syscall.S_IFREG || before.Uid != uint32(os.Geteuid()) || before.Mode&0077 != 0 || before.Nlink != 1 || before.Size > MaxBytes || (!empty && before.Size == 0) { return nil, nil, refuse("RECOVERY_HOLD_FILE_METADATA") }
	raw, err := io.ReadAll(io.LimitReader(f, MaxBytes+1))
	if err != nil || int64(len(raw)) != before.Size || syscall.Fstat(fd, &after) != nil || before.Dev != after.Dev || before.Ino != after.Ino || before.Mode != after.Mode || before.Uid != after.Uid || before.Nlink != after.Nlink || before.Size != after.Size || before.Mtim != after.Mtim || before.Ctim != after.Ctim { return nil, nil, refuse("RECOVERY_HOLD_FILE_CHANGED") }
	return raw, &before, nil
}

func directory(path string, readonly bool) error {
	fd, err := syscall.Open(path, syscall.O_RDONLY|syscall.O_DIRECTORY|syscall.O_NOFOLLOW, 0)
	if err != nil { return refuse("RECOVERY_HOLD_DIRECTORY") }; defer syscall.Close(fd)
	var st syscall.Stat_t; var fs syscall.Statfs_t
	if syscall.Fstat(fd, &st) != nil || st.Uid != uint32(os.Geteuid()) || st.Mode&0077 != 0 || syscall.Fstatfs(fd, &fs) != nil || (fs.Flags&1 != 0) != readonly { return refuse("RECOVERY_HOLD_MOUNT_UID_MODE") }
	return nil
}

func lockExisting(path string) (*os.File, *syscall.Stat_t, error) {
	fd, err := syscall.Open(path, syscall.O_RDWR|syscall.O_NOFOLLOW|syscall.O_NONBLOCK, 0)
	if err != nil { return nil, nil, refuse("RECOVERY_HOLD_LOCK") }
	f := os.NewFile(uintptr(fd), path)
	var st syscall.Stat_t
	if syscall.Fstat(fd, &st) != nil || st.Mode&syscall.S_IFMT != syscall.S_IFREG || st.Uid != uint32(os.Geteuid()) || st.Mode&0077 != 0 || st.Nlink != 1 || st.Size != 0 || syscall.Flock(fd, syscall.LOCK_EX|syscall.LOCK_NB) != nil { f.Close(); return nil, nil, refuse("RECOVERY_HOLD_EXCLUSIVE_CUSTODY") }
	return f, &st, nil
}

func pemBlock(raw []byte, kind string) ([]byte, error) {
	b, rest := pem.Decode(raw)
	if b == nil || b.Type != kind || len(b.Headers) != 0 || len(bytes.TrimSpace(rest)) != 0 { return nil, refuse("RECOVERY_PEM") }
	return b.Bytes, nil
}

func signedLine(out io.Writer, value map[string]any) error {
	raw, err := Canonical(value); if err != nil { return err }
	if len(raw) > MaxBytes { return refuse("RECOVERY_WIRE_SIZE") }
	_, err = fmt.Fprintln(out, string(raw)); return err
}

func ownHistory(root string, pub ed25519.PublicKey) ([]string, map[string]any, error) {
	entries, err := os.ReadDir(root); if err != nil { return nil, nil, refuse("RECOVERY_HOLD_HISTORY") }
	names := []string{}
	for _, entry := range entries {
		if entry.Name() == ".lock" { continue }
		if !regexp.MustCompile(`^[0-9]{8}-[0-9a-f]{32}\.json$`).MatchString(entry.Name()) { return nil, nil, refuse("RECOVERY_HOLD_FOREIGN_RESIDUE") }
		names = append(names, entry.Name())
	}
	sort.Strings(names); previous := ""; var last map[string]any
	for i, name := range names {
		raw, _, err := readRegular(filepath.Join(root, name), false); if err != nil { return nil, nil, err }
		record, err := Parse(raw); if err != nil || !Closed(record, "schema", "requestDigest", "proof", "checkpoint") || Text(record, "schema") != "sv-expired-policy-record:1" { return nil, nil, refuse("RECOVERY_HOLD_HISTORY") }
		proof, _, proofErr := Verify(Object(record,"proof"),ProofDomain,pub)
		proofRaw, _ := Canonical(record["proof"])
		checkpoint, _, err := Verify(Object(record, "checkpoint"), CheckpointDomain, pub)
		if proofErr != nil || Text(proof,"schema") != "sv-expired-policy-nonserving-proof:1" || Text(checkpoint,"proofDigest") != Hash(proofRaw) || Text(proof,"requestDigest") != Text(record,"requestDigest") { return nil,nil,refuse("RECOVERY_HOLD_HISTORY") }
		if err != nil || Number(checkpoint, "counter") != int64(i+1) || Text(checkpoint, "previousCheckpoint") != previous || Text(checkpoint, "requestDigest") != Text(record, "requestDigest") { return nil, nil, refuse("RECOVERY_HOLD_HISTORY") }
		if name != fmt.Sprintf("%08d-%s.json", i+1, Text(checkpoint, "operation")) { return nil, nil, refuse("RECOVERY_HOLD_HISTORY") }
		previous = Hash(raw); last = record
	}
	return names, last, nil
}

func durableRecord(root, name string, raw []byte) error {
	path := filepath.Join(root, name); temporary := path+".next"
	fd, err := syscall.Open(temporary, syscall.O_WRONLY|syscall.O_CREAT|syscall.O_EXCL|syscall.O_NOFOLLOW, 0600)
	if err != nil { return refuse("RECOVERY_HOLD_FOREIGN_RESIDUE") }
	f := os.NewFile(uintptr(fd), temporary)
	_, writeErr := f.Write(raw); syncErr := f.Sync(); closeErr := f.Close()
	if writeErr != nil || syncErr != nil || closeErr != nil { return refuse("RECOVERY_HOLD_PARTIAL_CHECKPOINT") }
	if os.Link(temporary, path) != nil { return refuse("RECOVERY_HOLD_CHECKPOINT_CONFLICT") }
	dir, err := os.Open(root); if err != nil { return refuse("RECOVERY_HOLD_PARTIAL_CHECKPOINT") }; defer dir.Close()
	if dir.Sync() != nil { return refuse("RECOVERY_HOLD_PARTIAL_CHECKPOINT") }
	if os.Remove(temporary) != nil || dir.Sync() != nil { return refuse("RECOVERY_HOLD_PARTIAL_CHECKPOINT") }
	return nil
}

// Run holds the actual preexisting journal flock through the checkpoint request.
// It writes only its separate candidate namespace, never peer policy/floor/CAS.
// Operator CID/image claims remain trusted operator custody, NOT TPM or a live M2.
func Run(request []byte, binding Binding, input io.Reader, out io.Writer) error {
	if os.Geteuid() != 1000 || !scopeID.MatchString(binding.Node) || binding.Tenant == "" || binding.Epoch == "" || !hex64.MatchString(binding.MembersDigest) || !hex64.MatchString(binding.HelperHash) || !hex64.MatchString(binding.AuthorizerHash) || !hex64.MatchString(binding.OperatorHash) { return refuse("RECOVERY_HOLD_UNBOUND") }
	for path, ro := range map[string]bool{binding.ConfigRoot:true, binding.TrustRoot:true, binding.StateRoot:false, binding.CustodyRoot:false} { if err := directory(path, ro); err != nil { return err } }
	journalLock, lockStat, err := lockExisting(filepath.Join(binding.StateRoot, ".lock")); if err != nil { return err }; defer journalLock.Close()
	custodyLock, _, err := lockExisting(filepath.Join(binding.CustodyRoot, ".lock")); if err != nil { return err }; defer custodyLock.Close()
	entries, err := os.ReadDir(binding.StateRoot); if err != nil || len(entries) != 3 { return refuse("RECOVERY_HOLD_ACTIVE_OR_UNKNOWN_JOURNAL") }
	for _, entry := range entries { if entry.Name() != ".lock" && entry.Name() != ".peer-policy" && entry.Name() != "identity.json" { return refuse("RECOVERY_HOLD_ACTIVE_OR_UNKNOWN_JOURNAL") } }
	public := map[string][]byte{}
	for _, name := range []string{"node-cert.pem", "client-ca.pem", "launch-signer.pub", "peer-policy.json"} {
		raw, _, err := readRegular(filepath.Join(binding.ConfigRoot, name), false); if err != nil { return err }; public[name] = raw
	}
	if len(public["launch-signer.pub"]) != 32 { return refuse("RECOVERY_SIGNER") }
	keyRaw, _, err := readRegular(filepath.Join(binding.ConfigRoot, "node-key.pem"), false); if err != nil { return err }
	keyDER, err := pemBlock(keyRaw, "PRIVATE KEY"); if err != nil { return err }
	k, err := x509.ParsePKCS8PrivateKey(keyDER); if err != nil { return refuse("RECOVERY_KEY") }
	key, ok := k.(ed25519.PrivateKey); if !ok { return refuse("RECOVERY_ALGORITHM") }
	nodeDER, err := pemBlock(public["node-cert.pem"], "CERTIFICATE"); if err != nil { return err }
	nodeCert, err := x509.ParseCertificate(nodeDER); if err != nil || !bytes.Equal(nodeCert.RawSubjectPublicKeyInfo, mustPKIX(key.Public())) { return refuse("RECOVERY_KEY_CONTINUITY") }
	caDER, err := pemBlock(public["client-ca.pem"], "CERTIFICATE"); if err != nil { return err }
	cpPub, _, err := readRegular(filepath.Join(binding.TrustRoot, "authorizer.pub"), false); if err != nil { return err }
	opPub, _, err := readRegular(filepath.Join(binding.TrustRoot, "operator.pub"), false); if err != nil { return err }
	if len(cpPub) != 32 || len(opPub) != 32 || Hash(cpPub) != binding.AuthorizerHash || Hash(opPub) != binding.OperatorHash || bytes.Equal(cpPub, opPub) || bytes.Equal(cpPub, key.Public().(ed25519.PublicKey)) || bytes.Equal(opPub, key.Public().(ed25519.PublicKey)) { return refuse("RECOVERY_ROLE_SEPARATION") }
	r, err := Parse(request); if err != nil || !Closed(r, "authorization", "operator") { return refuse("RECOVERY_REQUEST") }
	auth, authRaw, err := Verify(Object(r, "authorization"), AuthorizationDomain, cpPub); if err != nil { return err }
	if !Closed(auth, "schema", "role", "operation", "nonce", "counter", "issuedAt", "deadline", "candidateBudgetSeconds", "productionBudgetSeconds", "scenario", "tenantId", "epoch", "members", "caFingerprint", "cpDER", "cpFingerprint", "contexts", "contextGeneration", "revokedFingerprints", "publicationAllowed") || Text(auth,"schema") != "sv-expired-policy-authorization:1" || Text(auth,"role") != "recovery-authorizer" || auth["publicationAllowed"] != false || auth["productionBudgetSeconds"] != nil { return refuse("RECOVERY_AUTHORIZATION") }
	if Text(auth,"tenantId") != binding.Tenant || Text(auth,"epoch") != binding.Epoch || !operationID.MatchString(Text(auth,"operation")) || !hex64.MatchString(Text(auth,"nonce")) || Number(auth,"counter") < 1 || Number(auth,"counter") > 99999999 { return refuse("RECOVERY_SCOPE") }
	if Text(auth,"scenario") != "never-started" { return refuse("RECOVERY_HOLD_PARTIAL_RECONCILIATION_NOT_BOUND") }
	membersRaw, _ := Canonical(auth["members"])
	if len(Array(auth,"members")) != 3 || Hash(membersRaw) != binding.MembersDigest { return refuse("RECOVERY_MEMBERS") }
	var member map[string]any; previousID := ""
	for _, item := range Array(auth,"members") {
		m, ok := item.(map[string]any); if !ok || !Closed(m,"nodeId","ip","nodeFingerprint","priorC","targetC","priorP","targetP","floorSHA256","identitySHA256","policySHA256","configDigest","previousCheckpoint","priorPolicyExpiresAt") || Text(m,"nodeId") <= previousID { return refuse("RECOVERY_MEMBERS") }
		if !scopeID.MatchString(Text(m,"nodeId")) || Number(m,"priorP") < 1 || Number(m,"targetP") != Number(m,"priorP")+1 || Number(m,"priorC") < 1 || Number(m,"targetC") != Number(m,"priorC")+1 { return refuse("RECOVERY_GENERATIONS") }
		previousID = Text(m,"nodeId"); if previousID == binding.Node { member = m }
	}
	if member == nil || Number(member,"priorP") < 1 || Number(member,"priorP") >= 9007199254740991 || Number(member,"targetP") != Number(member,"priorP")+1 || Number(member,"priorC") < 1 || Number(member,"priorC") >= 9007199254740991 || Number(member,"targetC") != Number(member,"priorC")+1 { return refuse("RECOVERY_GENERATIONS") }
	cpDER, err := base64.StdEncoding.Strict().DecodeString(Text(auth,"cpDER")); if err != nil { return refuse("RECOVERY_LEAF") }
	now := Clock()
	if err := ValidateLeaves(caDER,cpDER,nodeDER,binding.Tenant,binding.Epoch,binding.Node,Text(member,"ip"),now); err != nil { return err }
	if Hash(caDER) != Text(auth,"caFingerprint") || Hash(cpDER) != Text(auth,"cpFingerprint") || Hash(nodeDER) != Text(member,"nodeFingerprint") { return refuse("RECOVERY_CERTIFICATE_PIN") }
	for _, fp := range Array(auth,"revokedFingerprints") { if fp == Hash(caDER) || fp == Hash(cpDER) || fp == Hash(nodeDER) { return refuse("RECOVERY_REVOKED") } }
	op, opRaw, err := Verify(Object(r,"operator"),OperatorDomain,opPub); if err != nil { return err }
	contextsRaw, _ := Canonical(auth["contexts"])
	if !Closed(op,"schema","role","proposalDigest","nodeId","containerId","imageId","helperSHA256","UID","lockDevice","lockInode","contextsDigest","issuedAt","deadline") || Text(op,"schema") != "sv-expired-policy-operator:1" || Text(op,"role") != "operator-custody-not-hardware" || Text(op,"proposalDigest") != Hash(authRaw) || Text(op,"nodeId") != binding.Node || Number(op,"deadline") != Number(auth,"deadline") || Number(op,"UID") != 1000 || Number(op,"lockDevice") != int64(lockStat.Dev) || Number(op,"lockInode") != int64(lockStat.Ino) || Text(op,"contextsDigest") != Hash(contextsRaw) || !hex64.MatchString(Text(op,"containerId")) || !hex64.MatchString(Text(op,"imageId")) { return refuse("RECOVERY_OPERATOR_BINDING") }
	exeInfo, statErr := os.Stat("/proc/self/exe"); if statErr != nil || !exeInfo.Mode().IsRegular() || exeInfo.Sys().(*syscall.Stat_t).Uid != 1000 || exeInfo.Mode().Perm()&0022 != 0 { return refuse("RECOVERY_HELPER_PROVENANCE") }
	exe, err := os.ReadFile("/proc/self/exe"); if err != nil || len(exe)>128*1024*1024 || Hash(exe) != binding.HelperHash || Text(op,"helperSHA256") != binding.HelperHash { return refuse("RECOVERY_HELPER_PROVENANCE") }
	names, last, err := ownHistory(binding.CustodyRoot,key.Public().(ed25519.PublicKey)); if err != nil { return err }
	name := fmt.Sprintf("%08d-%s.json",Number(auth,"counter"),Text(auth,"operation"))
	for _, existing := range names {
		if existing == name {
			raw, _, err := readRegular(filepath.Join(binding.CustodyRoot,existing),false); if err != nil { return err }; record, err := Parse(raw)
			if err != nil || Text(record,"requestDigest") != Hash(request) { return refuse("RECOVERY_REPLAY_MISMATCH") }
			return signedLine(out,map[string]any{"kind":"completed-candidate-checkpoint-replay","record":record})
		}
	}
	if err := Fresh(auth,now); err != nil { return err }; if err := Fresh(op,now); err != nil { return err }
	for _, der := range [][]byte{cpDER,nodeDER} { cert, _ := x509.ParseCertificate(der); if cert.NotAfter.Unix()-now <= Number(auth,"candidateBudgetSeconds")+660 { return refuse("RECOVERY_DEADLINE") } }
	if Number(auth,"candidateBudgetSeconds") < 1 || Number(auth,"candidateBudgetSeconds") > 60 || now+Number(auth,"candidateBudgetSeconds") >= Number(auth,"deadline") { return refuse("RECOVERY_DEADLINE") }
	previous := ""; if last != nil { raw, _, _ := readRegular(filepath.Join(binding.CustodyRoot,names[len(names)-1]),false); previous = Hash(raw) }
	if Number(auth,"counter") != int64(len(names)+1) || Text(member,"previousCheckpoint") != previous { return refuse("RECOVERY_COUNTER_REUSE") }
	identityRaw, _, err := readRegular(filepath.Join(binding.StateRoot,"identity.json"),false); if err != nil { return err }
	floorRaw, _, err := readRegular(filepath.Join(binding.StateRoot,".peer-policy"),false); if err != nil { return err }
	identity, err := ParseJournal(identityRaw); if err != nil || !Closed(identity,"Tenant","Node","Epoch") || Text(identity,"Tenant") != binding.Tenant || Text(identity,"Node") != binding.Node || Text(identity,"Epoch") != binding.Epoch { return refuse("RECOVERY_JOURNAL_IDENTITY") }
	floor, err := ParseJournal(floorRaw); if err != nil || !Closed(floor,"Version","Hash") || Number(floor,"Version") != Number(member,"priorP") || Text(floor,"Hash") != Hash(public["peer-policy.json"]) || Hash(floorRaw) != Text(member,"floorSHA256") || Hash(identityRaw) != Text(member,"identitySHA256") { return refuse("RECOVERY_AUTHENTICATED_FLOOR") }
	policy, err := ParseJournal(public["peer-policy.json"])
	if err != nil || !Closed(policy,"version","tenantId","nodeId","recoveryEpoch","expiresAt","clientFingerprints") || Number(policy,"version") != Number(member,"priorP") || Text(policy,"tenantId") != binding.Tenant || Text(policy,"nodeId") != binding.Node || Text(policy,"recoveryEpoch") != binding.Epoch || len(Array(policy,"clientFingerprints")) != 1 || Array(policy,"clientFingerprints")[0] != Hash(cpDER) { return refuse("RECOVERY_POLICY_BINDING") }
	expiry, err := time.Parse(time.RFC3339Nano,Text(policy,"expiresAt")); if err != nil || expiry.Unix() > now || expiry.Unix() != Number(member,"priorPolicyExpiresAt") { return refuse("RECOVERY_POLICY_NOT_EXPIRED") }
	config := map[string]any{}; for name, raw := range public { config[name] = Hash(raw) }; configRaw, _ := Canonical(config)
	if Hash(public["peer-policy.json"]) != Text(member,"policySHA256") || Hash(configRaw) != Text(member,"configDigest") { return refuse("RECOVERY_CONFIG_BINDING") }
	// The directory mounts are fixed by the operator; verify the locked inode is still published.
	if st, err := os.Lstat(filepath.Join(binding.StateRoot,".lock")); err != nil || st.Sys().(*syscall.Stat_t).Ino != lockStat.Ino { return refuse("RECOVERY_CUSTODY_CHANGED") }
	proof := map[string]any{"schema":"sv-expired-policy-nonserving-proof:1","assurance":"operator-custody-and-file-lock-not-hardware","serving":false,"servingPID":nil,"operation":auth["operation"],"nonce":auth["nonce"],"counter":auth["counter"],"tenantId":binding.Tenant,"epoch":binding.Epoch,"nodeId":binding.Node,"proposalDigest":Hash(authRaw),"requestDigest":Hash(request),"operatorDigest":Hash(opRaw),"helperSHA256":binding.HelperHash,"containerId":op["containerId"],"imageId":op["imageId"],"lockDevice":int64(lockStat.Dev),"lockInode":int64(lockStat.Ino),"lockHeldAtSigning":true,"observedAt":now,"deadline":auth["deadline"],"priorP":member["priorP"],"priorC":member["priorC"],"floorSHA256":Hash(floorRaw),"identitySHA256":Hash(identityRaw),"configDigest":Hash(configRaw),"previousCheckpoint":previous,"activationAllowed":false}
	proofEnvelope, err := Sign(proof,ProofDomain,key); if err != nil { return err }
	if err := signedLine(out,map[string]any{"kind":"nonserving-custody-proof","proof":proofEnvelope}); err != nil { return err }
	line := make(chan []byte,1)
	go func(){ reader := bufio.NewReader(io.LimitReader(input,MaxBytes+2)); raw, _ := reader.ReadBytes('\n'); line <- bytes.TrimSuffix(raw,[]byte{'\n'}) }()
	var ackRaw []byte
	select { case ackRaw = <-line: case <-time.After(time.Duration(Number(auth,"deadline")-Clock())*time.Second): return refuse("RECOVERY_CUSTODY_DEADLINE") }
	ackEnvelope, err := Parse(ackRaw); if err != nil { return err }; ack, _, err := Verify(ackEnvelope,AckDomain,cpPub); if err != nil { return err }
	if !Closed(ack,"schema","role","operation","proposalDigest","proofDigest","batchProofDigest","counter","deadline") || Text(ack,"schema") != "sv-expired-policy-checkpoint-request:1" || Text(ack,"role") != "recovery-authorizer" || Text(ack,"operation") != Text(auth,"operation") || Text(ack,"proposalDigest") != Hash(authRaw) || Number(ack,"counter") != Number(auth,"counter") || Number(ack,"deadline") != Number(auth,"deadline") || Clock() >= Number(auth,"deadline") || !hex64.MatchString(Text(ack,"batchProofDigest")) { return refuse("RECOVERY_CHECKPOINT_AUTHORIZATION") }
	proofBytes, _ := Canonical(proofEnvelope); if Text(ack,"proofDigest") != Hash(proofBytes) { return refuse("RECOVERY_CHECKPOINT_AUTHORIZATION") }
	// Recheck exact files while BOTH locks are still held. No serving assertion.
	for name, original := range public { current, _, err := readRegular(filepath.Join(binding.ConfigRoot,name),false); if err != nil || !bytes.Equal(original,current) { return refuse("RECOVERY_CUSTODY_CHANGED") } }
	for name, original := range map[string][]byte{"identity.json":identityRaw,".peer-policy":floorRaw} { current, _, err := readRegular(filepath.Join(binding.StateRoot,name),false); if err != nil || !bytes.Equal(original,current) { return refuse("RECOVERY_CUSTODY_CHANGED") } }
	checkpoint := map[string]any{"schema":"sv-expired-policy-candidate-checkpoint:1","operation":auth["operation"],"counter":auth["counter"],"requestDigest":Hash(request),"proofDigest":Hash(proofBytes),"ackDigest":Hash(ackRaw),"batchProofDigest":ack["batchProofDigest"],"previousCheckpoint":previous,"nodeId":binding.Node,"tenantId":binding.Tenant,"epoch":binding.Epoch,"checkpointAt":Clock(),"lockHeldThroughCheckpoint":true,"activationAllowed":false}
	checkpointEnvelope, err := Sign(checkpoint,CheckpointDomain,key); if err != nil { return err }
	record := map[string]any{"schema":"sv-expired-policy-record:1","requestDigest":Hash(request),"proof":proofEnvelope,"checkpoint":checkpointEnvelope}; recordRaw, err := Canonical(record); if err != nil { return err }
	if err := durableRecord(binding.CustodyRoot,name,recordRaw); err != nil { return err }
	return signedLine(out,map[string]any{"kind":"candidate-checkpoint-complete-lock-released-after-return","record":record})
}

func mustPKIX(pub any) []byte { raw, _ := x509.MarshalPKIXPublicKey(pub); return raw }

// ReadRequest refuses link, foreign UID, oversized and changing request files.
func ReadRequest(path string) ([]byte,error) { raw, _, err := readRegular(path,false); return raw,err }
