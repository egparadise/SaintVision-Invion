"""Report why interrupted A1 recovery remains on HOLD."""
import argparse
import json
from pathlib import Path

from a1_writer_fence import Writer, interrupted_a1_hold


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--expected-writer", required=True, type=Path)
    args = parser.parse_args()
    try:
        expected = json.loads(args.expected_writer.read_text(encoding="utf-8"))
        writer = Writer(expected["holderPlanDigest"], expected["token"], expected["generation"])
    except (OSError, ValueError, TypeError, KeyError):
        print("HOLD_WRITER_FENCE")
    else:
        print(interrupted_a1_hold(args.state / "a1-writer.sqlite3", writer))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
