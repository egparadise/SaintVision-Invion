// Package workspace handles bounded content, never host paths from a permit.
package workspace

import (
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	contracts "github.com/egparadise/SaintVision-Invion/packages/contracts-go"
	"github.com/egparadise/SaintVision-Invion/services/node-agent/internal/wire"
	"golang.org/x/text/cases"
	"golang.org/x/text/unicode/norm"
	"regexp"
	"sort"
	"strings"
	"unicode/utf8"
)

const MaxArchive = 65536
const MaxContent = 32768

var ErrInvalid = errors.New("NODE-0080: invalid bounded Workspace snapshot")
var reserved = regexp.MustCompile(`(?i)^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\..*)?$`)

func PathOK(p string) bool {
	if !utf8.ValidString(p) || !norm.NFC.IsNormalString(p) || utf8.RuneCountInString(p) > 1024 {
		return false
	}
	parts := strings.Split(p, "/")
	if len(parts) > 16 {
		return false
	}
	for _, part := range parts {
		if part == "" || part == "." || part == ".." || len(part) > 255 || strings.HasSuffix(part, ".") || strings.HasSuffix(part, " ") || reserved.MatchString(part) {
			return false
		}
		for _, c := range part {
			if c < 32 || strings.ContainsRune(`\:%<>"|?*`, c) {
				return false
			}
		}
	}
	return true
}

func Decode(raw []byte, id contracts.WorkspaceId) (contracts.WorkspaceSnapshot, error) {
	var s contracts.WorkspaceSnapshot
	if len(raw) > MaxArchive || wire.Validate("WorkspaceSnapshot", raw) != nil || json.Unmarshal(raw, &s) != nil || s.WorkspaceId != id || len(s.Files)+len(s.Directories) > 2048 {
		return s, ErrInvalid
	}
	names, dirs := map[string]bool{}, map[string]bool{}
	fold := cases.Fold()
	if !sort.StringsAreSorted(s.Directories) {
		return s, ErrInvalid
	}
	all := append([]string{}, s.Directories...)
	for _, p := range s.Directories {
		key := fold.String(p)
		if !PathOK(p) || names[key] {
			return s, ErrInvalid
		}
		names[key], dirs[p] = true, true
	}
	total, previous := 0, ""
	for _, f := range s.Files {
		key := fold.String(f.Path)
		chunk, err := base64.StdEncoding.Strict().DecodeString(f.DataBase64)
		sum := sha256.Sum256(chunk)
		total += len(chunk)
		if !PathOK(f.Path) || names[key] || f.Path <= previous || err != nil || base64.StdEncoding.EncodeToString(chunk) != f.DataBase64 || int64(len(chunk)) != f.SizeBytes || hex.EncodeToString(sum[:]) != f.Sha256 || total > MaxContent {
			return s, ErrInvalid
		}
		names[key], previous = true, f.Path
		all = append(all, f.Path)
	}
	for _, p := range all {
		parts := strings.Split(p, "/")
		for i := 1; i < len(parts); i++ {
			if !dirs[strings.Join(parts[:i], "/")] {
				return s, ErrInvalid
			}
		}
	}
	return s, nil
}

func Input(in *contracts.WorkspaceInput, id contracts.WorkspaceId) (contracts.WorkspaceSnapshot, error) {
	if in == nil {
		return contracts.WorkspaceSnapshot{}, ErrInvalid
	}
	raw, err := base64.StdEncoding.Strict().DecodeString(in.DataBase64)
	sum := sha256.Sum256(raw)
	if err != nil || base64.StdEncoding.EncodeToString(raw) != in.DataBase64 || int64(len(raw)) != in.SizeBytes || hex.EncodeToString(sum[:]) != in.Sha256 {
		return contracts.WorkspaceSnapshot{}, ErrInvalid
	}
	return Decode(raw, id)
}
