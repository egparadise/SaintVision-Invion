// Package migrationverify validates immutable migration inputs offline. It has
// no runtime, filesystem, network, signing, clock or operational adapters.
package migrationverify

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"regexp"
	"strconv"
	"time"
	"unicode/utf8"
)

const maxJSONBytes = 16 << 20
const maxJSONDepth = 128
const maxSafeInteger int64 = 9007199254740991

var integerToken = regexp.MustCompile(`^(0|-?[1-9][0-9]*)$`)

// ParseJSON rejects information that encoding/json would otherwise replace or
// collapse: malformed Unicode, duplicate keys and noncanonical integer tokens.
// Numbers remain json.Number, never float64. The input is not modified.
func ParseJSON(raw []byte) (any, error) {
	if len(raw) > maxJSONBytes || !utf8.Valid(raw) {
		return nil, errors.New("invalid UTF-8 or oversized JSON")
	}
	if err := checkEscapedUnicode(raw); err != nil {
		return nil, err
	}
	d := json.NewDecoder(bytes.NewReader(raw))
	d.UseNumber()
	v, err := readValue(d, 0)
	if err != nil {
		return nil, err
	}
	if _, err = d.Token(); err != io.EOF {
		return nil, errors.New("trailing JSON data")
	}
	return v, nil
}

// Scan escapes before decoding so an unpaired surrogate cannot become U+FFFD.
func checkEscapedUnicode(raw []byte) error {
	quoted := false
	for i := 0; i < len(raw); i++ {
		if raw[i] == '"' {
			quoted = !quoted
			continue
		}
		if !quoted || raw[i] != '\\' {
			continue
		}
		i++
		if i >= len(raw) {
			return errors.New("truncated escape")
		}
		if raw[i] != 'u' {
			continue
		}
		if i+4 >= len(raw) {
			return errors.New("truncated Unicode escape")
		}
		n, err := strconv.ParseUint(string(raw[i+1:i+5]), 16, 16)
		if err != nil {
			return errors.New("invalid Unicode escape")
		}
		i += 4
		if n >= 0xdc00 && n <= 0xdfff {
			return errors.New("unpaired low surrogate")
		}
		if n < 0xd800 || n > 0xdbff {
			continue
		}
		if i+6 >= len(raw) || raw[i+1] != '\\' || raw[i+2] != 'u' {
			return errors.New("unpaired high surrogate")
		}
		low, err := strconv.ParseUint(string(raw[i+3:i+7]), 16, 16)
		if err != nil || low < 0xdc00 || low > 0xdfff {
			return errors.New("invalid surrogate pair")
		}
		i += 6
	}
	return nil
}

func readValue(d *json.Decoder, depth int) (any, error) {
	if depth > maxJSONDepth {
		return nil, errors.New("JSON nesting limit")
	}
	t, err := d.Token()
	if err != nil {
		return nil, err
	}
	switch v := t.(type) {
	case json.Delim:
		switch v {
		case '{':
			m := map[string]any{}
			for d.More() {
				k, err := d.Token()
				if err != nil {
					return nil, err
				}
				key, ok := k.(string)
				if !ok {
					return nil, errors.New("non-string object key")
				}
				if _, exists := m[key]; exists {
					return nil, fmt.Errorf("duplicate key %q", key)
				}
				m[key], err = readValue(d, depth+1)
				if err != nil {
					return nil, err
				}
			}
			end, err := d.Token()
			if err != nil || end != json.Delim('}') {
				return nil, errors.New("unclosed object")
			}
			return m, nil
		case '[':
			a := []any{}
			for d.More() {
				x, err := readValue(d, depth+1)
				if err != nil {
					return nil, err
				}
				a = append(a, x)
			}
			end, err := d.Token()
			if err != nil || end != json.Delim(']') {
				return nil, errors.New("unclosed array")
			}
			return a, nil
		default:
			return nil, errors.New("unexpected delimiter")
		}
	case json.Number:
		if !integerToken.MatchString(string(v)) {
			return nil, errors.New("non-integer number token")
		}
		n, err := strconv.ParseInt(string(v), 10, 64)
		if err != nil || n < -maxSafeInteger || n > maxSafeInteger {
			return nil, errors.New("unsafe integer range")
		}
		return v, nil
	case string, bool, nil:
		return v, nil
	default:
		return nil, errors.New("unsupported JSON value")
	}
}

// CanonicalJSON implements C2: Go Marshal map ordering/HTML escaping, raw Unicode,
// U+2028/2029 escaping, no normalization and no trailing LF. Round-tripping
// through the strict reader also rejects floats and malformed programmatic input.
func CanonicalJSON(v any) ([]byte, error) {
	if err := validValue(v, 0); err != nil {
		return nil, err
	}
	return json.Marshal(v)
}

func validValue(v any, depth int) error {
	if depth > maxJSONDepth {
		return errors.New("JSON nesting limit")
	}
	switch x := v.(type) {
	case nil, bool:
	case string:
		if !utf8.ValidString(x) {
			return errors.New("invalid Unicode string")
		}
	case json.Number:
		if !integerToken.MatchString(string(x)) {
			return errors.New("non-integer number")
		}
		n, e := strconv.ParseInt(string(x), 10, 64)
		if e != nil || n < -maxSafeInteger || n > maxSafeInteger {
			return errors.New("unsafe integer")
		}
	case map[string]any:
		for k, v := range x {
			if !utf8.ValidString(k) {
				return errors.New("invalid Unicode key")
			}
			if e := validValue(v, depth+1); e != nil {
				return e
			}
		}
	case []any:
		for _, v := range x {
			if e := validValue(v, depth+1); e != nil {
				return e
			}
		}
	default:
		return fmt.Errorf("non-JSON value type %T", v)
	}
	return nil
}

func shaHex(b []byte) string { h := sha256.Sum256(b); return hex.EncodeToString(h[:]) }
func canonicalHash(v any) (string, error) {
	b, e := CanonicalJSON(v)
	if e != nil {
		return "", e
	}
	return shaHex(b), nil
}

func strictTime(s string) (time.Time, error) {
	t, e := time.Parse("2006-01-02T15:04:05Z", s)
	if e != nil || t.Format("2006-01-02T15:04:05Z") != s {
		return time.Time{}, errors.New("noncanonical UTC whole-second timestamp")
	}
	return t, nil
}
