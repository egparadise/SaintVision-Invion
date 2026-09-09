"""Cursor pagination.

Default limit 50, maximum 200 (PLAN-BACKEND-001). The cursor is the last row's
primary ID, which is a ULID and therefore already ordered by creation time — so
no separate sort key or opaque encoding is needed, and a client cannot page into
another tenant by editing it: the query is still inside the tenant scope.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from ..errors import VAL_CURSOR, InvError
from ..ids import is_id


@dataclass(frozen=True, slots=True)
class Page:
    items: Sequence[Any]
    next_cursor: str | None

    def to_dict(self, serialise) -> dict[str, Any]:
        return {
            "items": [serialise(item) for item in self.items],
            "nextCursor": self.next_cursor,
        }


def clamp_limit(requested: int | None, *, default: int = 50, maximum: int = 200) -> int:
    if requested is None:
        return default
    if requested < 1:
        raise InvError(VAL_CURSOR, "limit must be at least 1")
    return min(requested, maximum)


def validate_cursor(cursor: str | None) -> str | None:
    if cursor is None:
        return None
    if not is_id(cursor):
        raise InvError(VAL_CURSOR, "cursor is not a valid identifier")
    return cursor


def build_page(rows: Sequence[Any], *, limit: int, id_attr: str) -> Page:
    """Turn ``limit + 1`` fetched rows into a page and a next cursor.

    Fetching one extra row is how "is there more" is answered without a second
    count query, which would be both slower and racy.
    """
    if len(rows) > limit:
        items = rows[:limit]
        return Page(items=items, next_cursor=getattr(items[-1], id_attr))
    return Page(items=rows, next_cursor=None)
