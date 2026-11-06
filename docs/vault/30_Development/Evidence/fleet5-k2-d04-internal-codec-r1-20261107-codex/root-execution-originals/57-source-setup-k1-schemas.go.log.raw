package migrationverify

import (
	"embed"
	"encoding/json"
	"errors"
	"fmt"
	"regexp"
	"strings"

	"github.com/santhosh-tekuri/jsonschema/v6"
)

// Embedded resources are exact source blobs, including the seven schemas whose
// bytes have no $id. IDs are assigned by AddResource, never by rewriting them.
//
//go:embed resources
var resources embed.FS

type sourcePin struct {
	Path              string `json:"path"`
	PackagePath       string `json:"packagePath"`
	RawSHA256         string `json:"rawSHA256"`
	RawBytes          int    `json:"rawBytes"`
	OfflineResourceID string `json:"offlineResourceID"`
}

type sourceManifest struct {
	DesignSource string            `json:"designSource"`
	Pins         []sourcePin       `json:"pins"`
	RootSchemas  map[string]string `json:"rootSchemas"`
}

// Schemas is an immutable, compiled, offline closure. It supplies structural
// validation only. Schema success is never a signature or trust verdict.
type Schemas struct{ roots map[string]*jsonschema.Schema }

type noResolution struct{}

func (noResolution) Load(url string) (any, error) {
	return nil, fmt.Errorf("external schema resolution forbidden: %s", url)
}

func LoadSchemas() (*Schemas, error) {
	raw, e := resources.ReadFile("resources/source-pins.json")
	if e != nil {
		return nil, e
	}
	var m sourceManifest
	if e = json.Unmarshal(raw, &m); e != nil {
		return nil, e
	}
	if m.DesignSource != "8874b2dfe0dda9a019bd5f334636668290702e13" {
		return nil, errors.New("wrong design source")
	}
	c := jsonschema.NewCompiler()
	c.DefaultDraft(jsonschema.Draft2020)
	c.UseLoader(noResolution{})
	c.AssertFormat()
	c.UseRegexpEngine(pinnedRegexp)
	count := 0
	for _, p := range m.Pins {
		if p.OfflineResourceID == "" {
			continue
		}
		b, e := resources.ReadFile(p.PackagePath)
		if e != nil {
			return nil, e
		}
		if len(b) != p.RawBytes || shaHex(b) != p.RawSHA256 {
			return nil, fmt.Errorf("schema bytes changed: %s", p.Path)
		}
		v, e := ParseJSON(b)
		if e != nil {
			return nil, e
		}
		if e = c.AddResource(p.OfflineResourceID, v); e != nil {
			return nil, e
		}
		count++
	}
	if count != 17 {
		return nil, errors.New("incomplete schema closure")
	}
	// Compile every member of the closure, not only the latest API roots.
	for _, p := range m.Pins {
		if p.OfflineResourceID != "" {
			if _, e = c.Compile(p.OfflineResourceID); e != nil {
				return nil, e
			}
		}
	}
	s := &Schemas{roots: map[string]*jsonschema.Schema{}}
	for kind, id := range m.RootSchemas {
		v, e := c.Compile(id)
		if e != nil {
			return nil, e
		}
		s.roots[kind] = v
	}
	return s, nil
}

func (s *Schemas) Validate(kind string, v any) error {
	if s == nil {
		return errors.New("missing offline schema registry")
	}
	root, ok := s.roots[kind]
	if !ok || kind == "common" {
		return errors.New("unknown artifact kind")
	}
	if e := validValue(v, 0); e != nil {
		return e
	}
	if e := protocolStrings(v); e != nil {
		return e
	}
	if e := root.Validate(v); e != nil {
		return fmt.Errorf("%s schema: %w", kind, e)
	}
	return nil
}

// The pinned string contracts exclude NUL; other characters are governed by
// their exact field schema. Do not silently strengthen historic schema rules.
func protocolStrings(v any) error {
	switch x := v.(type) {
	case string:
		if strings.ContainsRune(x, 0) {
			return errors.New("protocol control character")
		}
	case map[string]any:
		for k, v := range x {
			if e := protocolStrings(k); e != nil {
				return e
			}
			if e := protocolStrings(v); e != nil {
				return e
			}
		}
	case []any:
		for _, v := range x {
			if e := protocolStrings(v); e != nil {
				return e
			}
		}
	}
	return nil
}

// The closed schema set uses only these eight ECMAScript-compatible patterns.
// Translate its literal Unicode NUL escape into RE2 notation without changing
// source bytes. Unknown regex syntax fails closed instead of approximating it.
func pinnedRegexp(pattern string) (jsonschema.Regexp, error) {
	switch pattern {
	case `^/[^/\u0000]+$`, `^/[^\u0000]*$`, `^[^\u0000]*$`,
		`^[0-9a-f]{128}$`, `^[0-9a-f]{40}$`, `^[0-9a-f]{64}$`,
		`^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$`, `^sha256:[0-9a-f]{64}$`:
		return regexp.Compile(strings.ReplaceAll(pattern, `\u0000`, `\x{0000}`))
	default:
		return nil, fmt.Errorf("unregistered schema regex: %q", pattern)
	}
}

const derivedDomain = "saintvision/derived/migration-cohort-projection-set/v1"

// ArtifactDigest selects the digest algorithm from the artifact kind. It is a
// byte calculation, not authentication. A supplied classification cannot select
// or override the algorithm and a digest is never an authority.
func ArtifactDigest(kind string, v any) (string, error) {
	switch kind {
	case "successor-plan", "operation-lease", "runtime-inventory", "migration-journal", "migration-event", "terminal-seal", "api-request", "api-response":
		return canonicalHash(v)
	case "cohort-projection-set":
		b, e := CanonicalJSON(v)
		if e != nil {
			return "", e
		}
		return shaHex(append([]byte(derivedDomain+"\x00"), b...)), nil
	default:
		return "", errors.New("unknown digest kind")
	}
}
