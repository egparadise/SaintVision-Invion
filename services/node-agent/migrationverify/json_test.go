package migrationverify

import (
	"encoding/json"
	"strings"
	"testing"
)

func TestStrictJSONRejectsLostInformation(t *testing.T) {
	bad := []string{`{"a":1,"a":2}`, `{"a":1,"\u0061":2}`, `{"x":{"k":1,"k":1}}`, `1.0`, `1e0`, `1E2`, `-0`, `9007199254740992`, `-9007199254740992`, `NaN`, `true false`, `"\ud800"`, `"\udc00"`, `"\ud800\u0061"`, `"\ud800\ud800"`, `"` + string([]byte{0xff}) + `"`, `"a` + string([]byte{0}) + `b"`, strings.Repeat("[", 130) + strings.Repeat("]", 130)}
	for _, raw := range bad {
		t.Run(raw, func(t *testing.T) {
			if _, e := ParseJSON([]byte(raw)); e == nil {
				t.Fatal("accepted ambiguous JSON")
			}
		})
	}
	for _, raw := range []string{`0`, `-1`, `9007199254740991`, `-9007199254740991`, `"\ud83d\ude00"`, `"\\ud800"`, `{"a":1,"A":2}`} {
		if _, e := ParseJSON([]byte(raw)); e != nil {
			t.Fatalf("valid JSON %s: %v", raw, e)
		}
	}
}

func TestCanonicalGoBytes(t *testing.T) {
	v, e := ParseJSON([]byte(`{"z":"<>&\u2028\u2029é한😀é","a":1}`))
	if e != nil {
		t.Fatal(e)
	}
	b, e := CanonicalJSON(v)
	if e != nil {
		t.Fatal(e)
	}
	want := `{"a":1,"z":"\u003c\u003e\u0026\u2028\u2029é한😀é"}`
	if string(b) != want {
		t.Fatalf("C2 bytes\ngot  %q\nwant %q", b, want)
	}
	for _, v := range []any{1.0, json.Number("1e0"), json.Number("-0"), string([]byte{0xff}), map[string]any{"x": uint64(1)}} {
		if _, e := CanonicalJSON(v); e == nil {
			t.Fatalf("accepted programmatic %T", v)
		}
	}
}

func TestStrictCalendar(t *testing.T) {
	for _, s := range []string{"2030-02-29T00:00:00Z", "2030-01-01T24:00:00Z", "2030-01-01T00:00:60Z", "2030-01-01T00:00:00+00:00", "2030-01-01T00:00:00.0Z"} {
		if _, e := strictTime(s); e == nil {
			t.Fatal(s)
		}
	}
	if _, e := strictTime("2032-02-29T00:00:00Z"); e != nil {
		t.Fatal(e)
	}
}
