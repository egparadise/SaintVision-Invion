#!/usr/bin/env python3
"""Operator metadata CLI: bounded public JSON stdin; PLAN unless explicit APPLY.

Only the explicitly named environment value supplies the operator connection.
The application discovers/opens no config, request or credential data files.
Ordinary libpq authentication/TLS (including operator-approved file references)
is part of that selected connection, not a universal no-file/sandbox guarantee.
The trusted operator deployment profile must bind host/port/database/user,
authentication/TLS expectations and approved driver environment/file references;
ambient service/default target selection is not an approved substitute.
No credentials in argv, subprocesses or Node transport. No exception text,
arguments, request body or connection info is ever printed. No TLS/auth rewrite.
"""

import argparse
import json
import os
from pathlib import Path
import re
import sys

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services/control-plane/src"))
from inv.errors import DomainError  # noqa: E402
from inv.fresh_cpu_admission import (  # noqa: E402
    MAX_REQUEST_BYTES, SAFE_ERRORS, apply_admission, plan_admission, prepare_request,
)


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's default includes rejected argv, which may contain a secret.
        raise DomainError("FRESH-0001", "Invalid command arguments", 422)


def _error(code):
    if type(code) is not str or code not in SAFE_ERRORS:
        code = "FRESH-0011"
    unknown = code == "FRESH-0010"
    result = {
        "status": "UNKNOWN_RECONCILE_REQUIRED" if unknown else "REFUSED",
        "code": code, "httpStatus": SAFE_ERRORS[code],
        "automaticRetryAllowed": False,
    }
    print(json.dumps(result, sort_keys=True), file=sys.stderr)
    return 3 if unknown else 2


def main(argv=None):
    apply_started = False
    try:
        parser = SafeParser(description=__doc__, allow_abbrev=False)
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--expected-plan-sha256")
        parser.add_argument("--dsn-env", default="SV_FRESH_NODE_OPERATOR_DSN")
        args = parser.parse_args(argv)
        if (not re.fullmatch(r"[A-Z][A-Z0-9_]{0,127}", args.dsn_env)
                or bool(args.expected_plan_sha256) != args.apply
                or (args.apply and not re.fullmatch(r"[0-9a-f]{64}", args.expected_plan_sha256))):
            return _error("FRESH-0001")
        raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
        item = prepare_request(raw)
        if args.apply and item.digest() != args.expected_plan_sha256:
            return _error("FRESH-0002")
        dsn = os.environ.get(args.dsn_env)
        if not dsn:
            return _error("FRESH-0012")
        # Trusted operator profile, forwarded intact: no authentication/TLS
        # parameter rewrite, discovery or claim of libpq filesystem confinement.
        # The DSN is never added to argv/output or interpolated into diagnostics.
        with psycopg.connect(dsn, autocommit=True) as conn:
            if args.apply:
                apply_started = True
                result = apply_admission(conn, raw, expected_plan_sha256=args.expected_plan_sha256)
            else:
                result = plan_admission(conn, raw)
        print(json.dumps(result, sort_keys=True, allow_nan=False))
        return 0
    except DomainError as error:
        return _error(error.code)
    except Exception:
        # Neither str/repr(error), arbitrary class names nor tracebacks are safe.
        return _error("FRESH-0010" if apply_started else "FRESH-0011")


if __name__ == "__main__":
    raise SystemExit(main())
