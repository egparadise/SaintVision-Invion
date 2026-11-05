"""V2 body encoding is separate from outer receipt canonicalization."""
import json
from pathlib import Path
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from test_lan_leaf_rotation import rotation
import peer_policy_phase as phase


def test_published_unicode_html_control_and_supplementary_vectors():
    path=Path(__file__).resolve().parent/'fixtures/fleet5-floor-v2-canonical-vectors.json'
    vectors=json.loads(path.read_bytes())['cases']
    cases={case['name']:case['body'] for case in vectors}
    assert len(vectors)==len(cases)==7
    assert set(cases)=={'ascii','unicode','html','controls','line-separators','supplementary','nested'}
    # Escaped code points make source/terminal encoding substitution detectable.
    assert cases['unicode']=={'\ud55c\uae00':'\ud14c\uc2a4\ud2b8 caf\u00e9','\u00e9':'na\u00efve','e\u0301':'decomposed'}
    assert {key.encode().hex() for key in cases['unicode']}=={'ed959ceab880','c3a9','65cc81'}
    assert cases['supplementary']=={'scalar':'\U0001f600\U0001d11e\U0010ffff','\U0001f9ed':'emoji'}
    assert cases['supplementary']['scalar'].encode().hex()=='f09f9880f09d849ef48fbfbf'
    assert cases['nested']['array'][-1]=={'&':'\u00e9\u2028\U0001f600'}
    assert cases['nested']['array'][-1]['&'].encode().hex()=='c3a9e280a8f09f9880'
    for vector in vectors:
        raw=phase.floor_canonical(vector['body'])
        assert raw.hex()==vector['expectedCanonicalUTF8Hex']
        assert not raw.endswith(b'\n')
    value={'html':'<>&','unicode':'한🦀\u2028\u2029'}
    encoded=phase.floor_canonical(value)
    assert b'\\u003c\\u003e\\u0026' in encoded
    assert '한🦀'.encode() in encoded and b'\\u2028\\u2029' in encoded
    assert rotation._canonical(value).endswith(b'\n')
    assert b'<>&' in rotation._canonical(value)  # existing outer convention retained


@pytest.mark.parametrize('invalid',['\ud800','\udfff',b'\xff',float('nan'),float('inf'),1.0,9007199254740992,{1:'non-string-key'}])
def test_v2_body_rejects_invalid_unicode_nonwire_values_and_overflow(invalid):
    with pytest.raises((ValueError,UnicodeError)):
        phase.floor_canonical({'value':invalid})


def test_v2_signature_does_not_verify_with_v1_domain_or_legacy_ascii_body():
    key=Ed25519PrivateKey.generate();body={'text':'한<>&🦀\u2028'}
    raw=phase.floor_canonical(body);signature=key.sign(phase.DOMAIN+raw)
    key.public_key().verify(signature,phase.DOMAIN+raw)
    from cryptography.exceptions import InvalidSignature
    with pytest.raises(InvalidSignature):key.public_key().verify(signature,b'saintvision/node-peer-policy-floor/v1\x00'+raw)
    with pytest.raises(InvalidSignature):key.public_key().verify(signature,phase.DOMAIN+phase.canonical(body))
