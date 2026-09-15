package runtime

import (
	"context"
	"encoding/base64"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"testing"

	contracts "github.com/egparadise/SaintVision-Invion/packages/contracts-go"
)

func TestTerminalHelperUsesNegotiatedVersionWithoutMutationRetry(t *testing.T) {
	for _, fail := range []bool{false, true} {
		t.Run(fmt.Sprint(fail), func(t *testing.T) {
			_, p, _ := fixture(t)
			record := Record{Claim: p.Claim, Name: "terminal-negotiation"}
			id, helper := strings.Repeat("a", 64), strings.Repeat("b", 64)
			frame := contracts.TerminalFrameInput{Sequence: 1, Operation: "input", Rows: 24, Columns: 80, Nonce: strings.Repeat("c", 64), DataBase64: "eAo="}
			starts, creates := 0, 0
			d := testDocker(t, func(w http.ResponseWriter, r *http.Request) {
				switch r.URL.Path {
				case "/version":
					fmt.Fprint(w, `{"ApiVersion":"1.41","MinAPIVersion":"1.12","Os":"linux"}`)
				case "/v1.41/containers/" + record.Name + "/json":
					value := inspection{ID: id, Name: record.Name}
					value.Config.Labels = labels(record)
					value.State.Running, value.State.Status = true, "running"
					json.NewEncoder(w).Encode(value)
				case "/v1.41/containers/" + id + "/exec":
					creates++
					var config struct {
						User                                                     string
						Privileged, AttachStdin, AttachStderr, AttachStdout, Tty bool
						Cmd, Env                                                 []string
					}
					if json.NewDecoder(r.Body).Decode(&config) != nil || config.User != "65532:65532" || config.Privileged || config.AttachStdin || config.AttachStderr || !config.AttachStdout || config.Tty || strings.Join(config.Cmd, " ") != "/inv-supervisor --terminal-frame" || len(config.Env) != 1 {
						t.Fatal("terminal helper gained unexpected authority")
					}
					raw, _ := base64.StdEncoding.DecodeString(strings.TrimPrefix(config.Env[0], "INV_TERMINAL_FRAME="))
					var got contracts.TerminalFrameInput
					if json.Unmarshal(raw, &got) != nil || got != frame {
						t.Fatal("frame changed")
					}
					json.NewEncoder(w).Encode(map[string]string{"Id": helper})
				case "/v1.41/exec/" + helper + "/start":
					starts++
					if fail {
						w.WriteHeader(500)
						return
					}
					data, _ := json.Marshal(contracts.NodeTerminalResult{CommandId: p.Claim.CommandId, SessionId: "00000000-0000-4000-8000-000000000001", Sequence: 1, Nonce: frame.Nonce})
					header := make([]byte, 8)
					header[0] = 1
					binary.BigEndian.PutUint32(header[4:], uint32(len(data)))
					w.Write(append(header, data...))
				default:
					t.Error("unexpected Docker endpoint: " + r.URL.Path)
					w.WriteHeader(404)
				}
			})
			out, err := d.Terminal(context.Background(), record, frame)
			if (err != nil) != fail || creates != 1 || starts != 1 {
				t.Fatalf("err=%v creates=%d starts=%d", err, creates, starts)
			}
			if !fail && (out.CommandId != p.Claim.CommandId || out.Nonce != frame.Nonce) {
				t.Fatal("wrong terminal result")
			}
		})
	}
}
