"""The deterministic test clock and the partition span it needs.

A plain module rather than ``conftest`` for the reason ``db_login.py`` gives:
``from conftest import ...`` is ambiguous between ``tests/conftest.py`` and
``tests/integration/conftest.py`` under pytest's default import mode.
"""

from __future__ import annotations

import datetime as dt

FROZEN_NOW = dt.datetime(2026, 9, 9, 7, 0, 0, tzinfo=dt.timezone.utc)


def frozen_clock_span_months(now: dt.datetime | None = None) -> int:
    """Whole months from FROZEN_NOW's month to the wall-clock month (never negative).

    The disposable test database provisions this many months after FROZEN_NOW's
    month so every pinned test clock between FROZEN_NOW and today stays routable
    after a calendar rollover; the migration supplies the wall-clock lead beyond it.
    """
    current = now or dt.datetime.now(dt.timezone.utc)
    span = (current.year - FROZEN_NOW.year) * 12 + current.month - FROZEN_NOW.month
    return max(0, span)
