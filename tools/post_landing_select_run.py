#!/usr/bin/env python3
"""Print the run ids in ``gh run list --json`` output that match a head, event and title.

The post-landing guard (tools/post_landing_lane_guard.sh) needs "exactly one run of this
workflow, at this landed SHA, from this dispatch, with this correlation id" -- and it needs the
answer to be checkable.  Doing the selection here rather than in an embedded ``--jq`` string
keeps one readable definition of "matching run", lets the shell count the lines, and lets
tests/test_post_landing_lane_guard.py drive the whole gate with a fake ``gh`` that only has to
print rows.

Reads the JSON array on stdin; prints one id per line, newest first as ``gh`` ordered them.
"""

from __future__ import annotations

import argparse
import json
import sys


def matching(rows: object, sha: str, event: str, title: str) -> list[str]:
    if not isinstance(rows, list):
        raise ValueError("gh run list output must be a JSON array")
    found = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("every run row must be an object")
        if row.get("headSha") == sha and row.get("event") == event and row.get("displayTitle") == title:
            run_id = row.get("databaseId")
            if not isinstance(run_id, int) or isinstance(run_id, bool) or run_id <= 0:
                raise ValueError("a matching run has no usable databaseId")
            found.append(str(run_id))
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--event", required=True)
    parser.add_argument("--title", required=True)
    args = parser.parse_args(argv)
    try:
        rows = json.loads(sys.stdin.read() or "[]")
        for run_id in matching(rows, args.sha, args.event, args.title):
            print(run_id)
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"post-landing run selection refused: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
