import re
import secrets
import time

ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def new_id(prefix: str) -> str:
    if not re.fullmatch(r"[a-z]{3,4}", prefix):
        raise ValueError("ID prefix must be 3 or 4 lowercase letters")
    value = (time.time_ns() // 1_000_000 << 80) | secrets.randbits(80)
    encoded = ""
    for _ in range(26):
        encoded = ALPHABET[value & 31] + encoded
        value >>= 5
    return f"{prefix}_{encoded}"
