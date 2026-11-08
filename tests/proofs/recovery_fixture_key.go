// Isolated hosted fixture setup only. Private bytes are created inside the
// Node's local /config mount and are never returned to the CP harness.
package main

import (
	"crypto/ed25519"
	"crypto/rand"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/base64"
	"encoding/json"
	"encoding/pem"
	"os"
	"time"
)

func main() {
	if os.Geteuid() != 1000 || len(os.Args) != 2 { os.Exit(1) }
	if os.Args[1] == "--isolated-fixture-hold" { for { time.Sleep(time.Hour) } }
	if os.Args[1] != "--isolated-fixture-keygen" { os.Exit(1) }
	pub, key, err := ed25519.GenerateKey(rand.Reader); if err != nil { os.Exit(1) }
	raw, err := x509.MarshalPKCS8PrivateKey(key); if err != nil { os.Exit(1) }
	f, err := os.OpenFile("/config/node-key.pem",os.O_WRONLY|os.O_CREATE|os.O_EXCL,0600); if err != nil { os.Exit(1) }
	if _, err = f.Write(pem.EncodeToMemory(&pem.Block{Type:"PRIVATE KEY",Bytes:raw})); err != nil || f.Sync() != nil || f.Close() != nil { os.Exit(1) }
	csr, err := x509.CreateCertificateRequest(rand.Reader,&x509.CertificateRequest{Subject:pkix.Name{CommonName:"isolated-candidate-Node"}},key); if err != nil { os.Exit(1) }
	_ = json.NewEncoder(os.Stdout).Encode(map[string]string{"publicKey":base64.StdEncoding.EncodeToString(pub),"csr":base64.StdEncoding.EncodeToString(csr)})
}
