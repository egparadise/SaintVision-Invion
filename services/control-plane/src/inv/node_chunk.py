"""Bounded byte validation shared by Node readers; never grants read authority.

The caller must pin/authenticate the transport and recheck current authority at
commit. A valid chunk digest alone does not establish the complete object hash.
"""

import base64
import binascii
import hashlib

from .contracts import validate_contract
from .errors import DomainError

CHUNK_BYTES = 256 * 1024


def verified_chunk(request, result):
    validate_contract("NodeChunkInput", request)
    validate_contract("NodeChunkResult", result)
    if request["offset"] >= request["sizeBytes"]:
        raise DomainError("NODE-0052", "Invalid transfer range", 422)
    if any(result[k] != v for k, v in request.items()):
        raise DomainError("NODE-0052", "Transfer response scope differs", 403)
    # Validate schema/encoded length before allocating decoded bytes.
    try:
        chunk = base64.b64decode(result["dataBase64"], validate=True)
    except (ValueError, binascii.Error):
        raise DomainError("NODE-0052", "Invalid transfer bytes", 422) from None
    if (
        len(chunk) != min(CHUNK_BYTES, request["sizeBytes"] - request["offset"])
        or hashlib.sha256(chunk).hexdigest() != result["chunkSha256"]
        or base64.b64encode(chunk).decode("ascii") != result["dataBase64"]
    ):
        raise DomainError("VERIFY-0010", "Transferred chunk differs", 422)
    return chunk
