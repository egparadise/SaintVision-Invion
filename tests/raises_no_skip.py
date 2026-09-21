"""Assertions for failures that must never be downgraded to pytest skips."""

from __future__ import annotations

import re
from contextlib import contextmanager
from types import SimpleNamespace

import pytest


@contextmanager
def raises_without_skip(expected, match=None):
    """Like ``pytest.raises`` but treats pytest's BaseException skip as failure."""
    expected_types = expected if isinstance(expected, tuple) else (expected,)
    expected_names = ", ".join(t.__name__ for t in expected_types)

    def contains_skip(exc):
        if isinstance(exc, pytest.skip.Exception):
            return True
        if isinstance(exc, BaseExceptionGroup):
            return any(contains_skip(child) for child in exc.exceptions)
        return False

    captured = SimpleNamespace(value=None)
    try:
        yield captured
    except BaseException as exc:
        if contains_skip(exc):
            pytest.fail(f"unexpected skip while expecting {expected_names}: {exc}")
        if not isinstance(exc, expected_types):
            raise
        if match is not None and re.search(match, str(exc)) is None:
            pytest.fail(f"failure did not match {match!r}: {exc}")
        captured.value = exc
    else:
        pytest.fail(f"expected {expected_names}, got no exception")
