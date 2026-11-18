"""Local A1 writer-fence prerequisite. No signing or recovery execution entry point."""
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Writer:
    plan_digest: str
    token: str
    generation: int

    def __post_init__(self):
        if not isinstance(self.plan_digest, str) or not self.plan_digest:
            raise ValueError("Missing plan digest")
        if not isinstance(self.token, str) or not self.token:
            raise ValueError("Missing fence token")
        if type(self.generation) is not int or self.generation < 1:
            raise ValueError("Invalid fence generation")


def initialize(path: Path) -> None:
    """Provision a new ledger once in the authority custodian's private directory."""
    with path.open("xb"):
        pass
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("""CREATE TABLE fence (
            singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
            plan_digest TEXT NOT NULL, token TEXT NOT NULL,
            generation INTEGER NOT NULL CHECK (generation >= 1)
        )""")


def transfer(path: Path, previous: Writer | None, plan_digest: str, token: str) -> Writer:
    """Compare and swap ownership under the database write lock."""
    generation = 1 if previous is None else previous.generation + 1
    successor = Writer(plan_digest, token, generation)
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=rw", uri=True)) as db, db:
        db.execute("BEGIN IMMEDIATE")
        if previous is None:
            changed = db.execute(
                "INSERT INTO fence SELECT 1, ?, ?, 1 WHERE NOT EXISTS (SELECT 1 FROM fence)",
                (plan_digest, token),
            )
        else:
            changed = db.execute(
                """UPDATE fence SET plan_digest=?, token=?, generation=?
                   WHERE singleton=1 AND plan_digest=? AND token=? AND generation=?""",
                (plan_digest, token, generation, previous.plan_digest, previous.token,
                 previous.generation),
            )
        if changed.rowcount != 1:
            raise ValueError("Writer fence changed")
    return successor


def interrupted_a1_hold(path: Path, expected: Writer) -> str:
    """Observe ownership afresh. The signer has no authoritative ceremony ledger yet."""
    try:
        with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
            row = db.execute(
                "SELECT plan_digest, token, generation FROM fence WHERE singleton=1"
            ).fetchone()
    except sqlite3.Error:
        return "HOLD_WRITER_FENCE"
    if row != (expected.plan_digest, expected.token, expected.generation):
        return "HOLD_WRITER_FENCE"
    return "HOLD_CUSTODY_UNRESOLVED"
