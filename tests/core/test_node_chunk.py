import base64
import hashlib

import pytest

from inv.errors import DomainError
from inv.node_chunk import CHUNK_BYTES, verified_chunk


def exchange(data=b"x", *, offset=0, size=None):
    request = dict(sha256="a" * 64, sizeBytes=len(data) if size is None else size,
                   offset=offset, nonce="b" * 64)
    result = dict(request, dataBase64=base64.b64encode(data).decode(),
                  chunkSha256=hashlib.sha256(data).hexdigest())
    return request, result


@pytest.mark.parametrize("length", [1, CHUNK_BYTES - 1, CHUNK_BYTES])
def test_exact_tail_and_full_chunk(length):
    data = b"x" * length
    request, result = exchange(data, offset=CHUNK_BYTES, size=CHUNK_BYTES + length)
    assert verified_chunk(request, result) == data


@pytest.mark.parametrize("field,value", [
    ("sha256", "c" * 64), ("nonce", "c" * 64), ("offset", 1), ("sizeBytes", 2),
])
def test_scope_replay_rejected(field, value):
    request, result = exchange()
    result[field] = value
    with pytest.raises(DomainError) as error:
        verified_chunk(request, result)
    assert error.value.status == 403


@pytest.mark.parametrize("fault", ["short", "long", "hash", "invalid", "pad-bits"])
def test_bytes_must_match_exact_range_and_canonical_encoding(fault):
    request, result = exchange()
    if fault == "short":
        request["sizeBytes"] = result["sizeBytes"] = 2
    elif fault == "long":
        result["dataBase64"] = base64.b64encode(b"xx").decode()
        result["chunkSha256"] = hashlib.sha256(b"xx").hexdigest()
    elif fault == "hash":
        result["chunkSha256"] = "0" * 64
    elif fault == "invalid":
        result["dataBase64"] = "!!!!"
    else:
        result["dataBase64"] = "eB=="  # Decodes to x but has nonzero pad bits.
    with pytest.raises(DomainError):
        verified_chunk(request, result)


@pytest.mark.parametrize("offset,size", [(0, 0), (1, 1), (2, 1)])
def test_empty_or_past_end_range_is_not_byte_evidence(offset, size):
    request, result = exchange(b"", offset=offset, size=size)
    with pytest.raises(DomainError):
        verified_chunk(request, result)


def test_oversized_response_rejected_before_decode(monkeypatch):
    request, result = exchange()
    result["dataBase64"] = "A" * 349529
    monkeypatch.setattr(base64, "b64decode", lambda *a, **k: pytest.fail("decoded oversized input"))
    with pytest.raises(DomainError):
        verified_chunk(request, result)
