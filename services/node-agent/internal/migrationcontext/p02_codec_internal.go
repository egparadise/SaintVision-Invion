package migrationcontext

// Checked lexical algebra is internal to this codec. It is never an authenticated
// boundary record, arbitrary callback, or constructor for an opaque policy.
import "bytes"

const (
	p02EnvelopeLimit       = 2 << 20
	p02PayloadLimit        = 16 << 20
	p02ArtifactLimit       = 256 << 20
	p02SafeInteger   int64 = 9007199254740991
	p02MaxEpoch      int64 = 253402300799
	p02Format              = "fleet5-p02-registry-candidate:2"
	p02Purpose             = "installed-policy-registry"
	p02Domain              = "fleet5/p02/installed-policy-registry/candidate/v2"
)

type p02Value struct {
	kind    byte
	text    string
	integer int64
	boolean bool
	object  []p02Field
	array   []p02Value
}
type p02Field struct {
	key   string
	value p02Value
}
type p02Parser struct {
	raw               []byte
	pos, nodes, limit int
}

func p02ASCII(s string) bool {
	for _, c := range s {
		if c < 32 || c > 126 {
			return false
		}
	}
	return true
}
func p02Digit(c byte) int64 {
	if c >= '0' && c <= '9' {
		return int64(c - '0')
	}
	return -1
}
func p02HexDigit(c byte) int64 {
	if c >= '0' && c <= '9' {
		return int64(c - '0')
	}
	if c >= 'a' && c <= 'f' {
		return int64(c-'a') + 10
	}
	return -1
}
func p02Hex(s string, n int, nonzero bool) bool {
	if len(s) == 0 || len(s)%2 != 0 || n > 0 && len(s) != n {
		return false
	}
	nz := false
	for i := 0; i < len(s); i++ {
		if p02HexDigit(s[i]) < 0 {
			return false
		}
		if s[i] != '0' {
			nz = true
		}
	}
	return !nonzero || nz
}
func p02Decimal(n int64) string {
	if n == 0 {
		return "0"
	}
	neg := n < 0
	if neg {
		n = -n
	}
	b := make([]byte, 0, 20)
	for n > 0 {
		b = append(b, byte(n%10)+'0')
		n /= 10
	}
	if neg {
		b = append(b, '-')
	}
	for i, j := 0, len(b)-1; i < j; i, j = i+1, j-1 {
		b[i], b[j] = b[j], b[i]
	}
	return string(b)
}
func p02String(s string) p02Value      { return p02Value{kind: 's', text: s} }
func p02Integer(i int64) p02Value      { return p02Value{kind: 'i', integer: i} }
func p02Boolean(b bool) p02Value       { return p02Value{kind: 'b', boolean: b} }
func p02Object(f ...p02Field) p02Value { return p02Value{kind: 'o', object: f} }
func p02Array(v []p02Value) p02Value   { return p02Value{kind: 'a', array: v} }
func p02Get(v p02Value, key string) p02Value {
	for _, f := range v.object {
		if f.key == key {
			return f.value
		}
	}
	return p02Value{}
}

func (p *p02Parser) quoted() (string, bool) {
	if p.pos >= len(p.raw) || p.raw[p.pos] != '"' {
		return "", false
	}
	p.pos++
	b := make([]byte, 0)
	for p.pos < len(p.raw) {
		c := p.raw[p.pos]
		p.pos++
		if c == '"' {
			return string(b), true
		}
		if c == '\\' {
			if p.pos >= len(p.raw) {
				return "", false
			}
			c = p.raw[p.pos]
			p.pos++
			if c == 'u' {
				if len(p.raw)-p.pos < 4 {
					return "", false
				}
				code := int64(0)
				for j := 0; j < 4; j++ {
					d := p02HexDigit(p.raw[p.pos+j])
					if d < 0 && p.raw[p.pos+j] >= 'A' && p.raw[p.pos+j] <= 'F' {
						d = int64(p.raw[p.pos+j]-'A') + 10
					}
					if d < 0 {
						return "", false
					}
					code = code*16 + d
				}
				p.pos += 4
				if code < 32 || code > 126 {
					return "", false
				}
				c = byte(code)
			} else if c != '"' && c != '\\' && c != '/' {
				return "", false
			}
		}
		if c < 32 || c > 126 {
			return "", false
		}
		if len(b) >= p.limit {
			return "", false
		}
		b = append(b, c)
	}
	return "", false
}
func (p *p02Parser) literal(s string) bool {
	if len(p.raw)-p.pos < len(s) {
		return false
	}
	if string(p.raw[p.pos:p.pos+len(s)]) != s {
		return false
	}
	p.pos += len(s)
	return true
}
func (p *p02Parser) value(depth int) (p02Value, bool) {
	if depth > 32 || p.nodes <= 0 || p.pos >= len(p.raw) {
		return p02Value{}, false
	}
	p.nodes--
	c := p.raw[p.pos]
	if c == '"' {
		s, ok := p.quoted()
		return p02String(s), ok
	}
	if c == 't' {
		return p02Boolean(true), p.literal("true")
	}
	if c == 'f' {
		return p02Boolean(false), p.literal("false")
	}
	if c == 'n' {
		return p02Value{kind: 'n'}, p.literal("null")
	}
	if c == '{' {
		p.pos++
		v := p02Object()
		previous := ""
		count := 0
		if p.pos < len(p.raw) && p.raw[p.pos] == '}' {
			p.pos++
			return v, true
		}
		for {
			if p.nodes <= 0 {
				return p02Value{}, false
			}
			p.nodes--
			key, ok := p.quoted()
			if !ok || count > 0 && key <= previous {
				return p02Value{}, false
			}
			if p.pos >= len(p.raw) || p.raw[p.pos] != ':' {
				return p02Value{}, false
			}
			p.pos++
			child, ok := p.value(depth + 1)
			if !ok {
				return p02Value{}, false
			}
			v.object = append(v.object, p02Field{key, child})
			previous = key
			count++
			if p.pos >= len(p.raw) {
				return p02Value{}, false
			}
			end := p.raw[p.pos]
			p.pos++
			if end == '}' {
				return v, true
			}
			if end != ',' {
				return p02Value{}, false
			}
		}
	}
	if c == '[' {
		p.pos++
		v := p02Array(nil)
		if p.pos < len(p.raw) && p.raw[p.pos] == ']' {
			p.pos++
			return v, true
		}
		for {
			child, ok := p.value(depth + 1)
			if !ok {
				return p02Value{}, false
			}
			v.array = append(v.array, child)
			if p.pos >= len(p.raw) {
				return p02Value{}, false
			}
			end := p.raw[p.pos]
			p.pos++
			if end == ']' {
				return v, true
			}
			if end != ',' {
				return p02Value{}, false
			}
		}
	}
	neg := false
	if c == '-' {
		neg = true
		p.pos++
		if p.pos >= len(p.raw) {
			return p02Value{}, false
		}
		c = p.raw[p.pos]
	}
	if p02Digit(c) < 0 {
		return p02Value{}, false
	}
	zero := c == '0'
	n := int64(0)
	count := 0
	for p.pos < len(p.raw) {
		d := p02Digit(p.raw[p.pos])
		if d < 0 {
			break
		}
		if count > 0 && zero || n > (p02SafeInteger-d)/10 {
			return p02Value{}, false
		}
		n = n*10 + d
		p.pos++
		count++
	}
	if neg {
		if n == 0 {
			return p02Value{}, false
		}
		n = -n
	}
	return p02Integer(n), true
}
func p02AppendString(out []byte, s string, c2 bool) ([]byte, bool) {
	if !p02ASCII(s) {
		return nil, false
	}
	out = append(out, '"')
	for i := 0; i < len(s); i++ {
		c := s[i]
		if c == '"' || c == '\\' {
			out = append(out, '\\', c)
		} else if c2 && (c == '&' || c == '<' || c == '>') {
			digits := "0123456789abcdef"
			out = append(out, '\\', 'u', '0', '0', digits[c/16], digits[c%16])
		} else {
			out = append(out, c)
		}
	}
	return append(out, '"'), true
}
func p02EncodeValue(out []byte, v p02Value, c2 bool, depth int) ([]byte, bool) {
	if depth > 32 {
		return nil, false
	}
	switch v.kind {
	case 's':
		return p02AppendString(out, v.text, c2)
	case 'i':
		if v.integer < -p02SafeInteger || v.integer > p02SafeInteger {
			return nil, false
		}
		return append(out, []byte(p02Decimal(v.integer))...), true
	case 'b':
		if v.boolean {
			return append(out, []byte("true")...), true
		}
		return append(out, []byte("false")...), true
	case 'n':
		return append(out, []byte("null")...), true
	case 'a':
		out = append(out, '[')
		for i, x := range v.array {
			if i > 0 {
				out = append(out, ',')
			}
			var ok bool
			out, ok = p02EncodeValue(out, x, c2, depth+1)
			if !ok {
				return nil, false
			}
		}
		return append(out, ']'), true
	case 'o':
		fields := append([]p02Field(nil), v.object...)
		for i := 1; i < len(fields); i++ {
			for j := i; j > 0 && fields[j].key < fields[j-1].key; j-- {
				fields[j], fields[j-1] = fields[j-1], fields[j]
			}
		}
		out = append(out, '{')
		for i, f := range fields {
			if i > 0 {
				if f.key == fields[i-1].key {
					return nil, false
				}
				out = append(out, ',')
			}
			var ok bool
			out, ok = p02AppendString(out, f.key, c2)
			if !ok {
				return nil, false
			}
			out = append(out, ':')
			out, ok = p02EncodeValue(out, f.value, c2, depth+1)
			if !ok {
				return nil, false
			}
		}
		return append(out, '}'), true
	}
	return nil, false
}
func p02Encode(v p02Value, c2 bool) ([]byte, bool) { return p02EncodeValue(nil, v, c2, 0) }
func p02Decode(raw []byte, limit int, c2 bool) (p02Value, bool) {
	// Byte limit is checked before parser/string/tree allocations.
	if len(raw) == 0 || len(raw) > limit {
		return p02Value{}, false
	}
	p := p02Parser{raw: raw, nodes: 100000, limit: limit}
	v, ok := p.value(0)
	if !ok || p.pos != len(raw) {
		return p02Value{}, false
	}
	encoded, ok := p02Encode(v, c2)
	if !ok || !bytes.Equal(encoded, raw) {
		return p02Value{}, false
	}
	return v, true
}
func p02Same(a, b p02Value) bool {
	x, ok := p02Encode(a, false)
	if !ok {
		return false
	}
	y, ok := p02Encode(b, false)
	return ok && bytes.Equal(x, y)
}
