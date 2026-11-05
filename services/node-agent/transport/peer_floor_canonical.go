package transport

import (
	"encoding/json"
	"errors"
	"strconv"
	"unicode/utf8"
)

// CanonicalPeerFloorBody preserves json.Marshal's sorted map keys, compact UTF8,
// HTML/U+2028/U+2029 escaping and absence of a body newline. M2 has only exact
// integer numbers; floats and invalid UTF8 are rejected, not silently rewritten.
func CanonicalPeerFloorBody(body map[string]any) ([]byte, error) {
	invalid := errors.New("NODE-0041: noncanonical M2 body")
	var check func(any) bool
	integer := func(v int64) bool { return v >= -9007199254740991 && v <= 9007199254740991 }
	check = func(value any) bool {
		switch v := value.(type) {
		case nil, bool:
			return true
		case string:
			return utf8.ValidString(v)
		case int:
			return integer(int64(v))
		case int64:
			return integer(v)
		case uint32:
			return true
		case json.Number:
			n, err := strconv.ParseInt(string(v), 10, 64)
			return err == nil && integer(n) && strconv.FormatInt(n, 10) == string(v)
		case []any:
			for _, item := range v {
				if !check(item) {
					return false
				}
			}
			return true
		case map[string]any:
			for key, item := range v {
				if !utf8.ValidString(key) || !check(item) {
					return false
				}
			}
			return true
		default:
			return false
		}
	}
	if !check(body) {
		return nil, invalid
	}
	return json.Marshal(body)
}
