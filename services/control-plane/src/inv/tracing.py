"""Public request correlation; never an authentication or Evidence authority."""

import re
import secrets

PARENT = re.compile(rb"00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})")


def nonzero_id(size):
    while True:
        value = secrets.token_hex(size)
        if int(value, 16):
            return value


def request_trace(headers):
    values = [v for k, v in headers if k == b"traceparent"]
    match = PARENT.fullmatch(values[0]) if len(values) == 1 else None
    if match and int(match[1], 16) and int(match[2], 16):
        trace_id = match[1].decode("ascii")
        # Only the sampled bit is defined by the supported version 00 profile.
        flags = f"{int(match[3], 16) & 1:02x}"
    else:
        trace_id, flags = nonzero_id(16), "00"
    return trace_id, f"00-{trace_id}-{nonzero_id(8)}-{flags}"
