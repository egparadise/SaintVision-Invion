"""Local, synthetic A1 evidence for an independently validated R2 plan."""
from contextlib import closing, contextmanager
from pathlib import Path
import re
import sqlite3

from tools.check_fleet5_authority_replacement_r2 import plan_digest


def _expected(plan):
    leaves = {member["nodeID"]: member["plannedLeafSHA256"] for member in plan["members"]}
    if len(leaves) != len(plan["members"]) or not leaves or "control-plane" in leaves or "" in leaves:
        raise ValueError("Invalid planned subjects")
    leaves["control-plane"] = plan["controlPlaneClient"]["plannedLeafSHA256"]
    return {"": plan["newAuthority"]["caPublicKeySHA256"], **leaves}


@contextmanager
def _transaction(path, plan, write):
    digest = plan_digest(plan)
    if plan["operationManifest"] and plan["operationManifest"]["planDigest"] != digest:
        raise ValueError("Plan digest mismatch")
    fence = plan["writerFence"]
    mode = "rw" if write else "ro"
    uri = Path(path).resolve().as_uri() + "?mode=" + mode
    with closing(sqlite3.connect(uri, uri=True)) as db, db:
        db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
        current = db.execute("SELECT plan_digest, token, generation FROM fence WHERE singleton=1").fetchone()
        if current != (digest, fence["token"], fence["generation"]):
            raise ValueError("Writer fence changed")
        yield db, digest


def record(path, plan, event_id, subject, fingerprint):
    """Record one observed event. Empty subject denotes the CA public key."""
    expected = _expected(plan)
    if not isinstance(event_id, str) or not event_id.strip():
        raise ValueError("Missing event identity")
    if not isinstance(fingerprint, str) or not re.fullmatch("[0-9a-f]{64}", fingerprint):
        raise ValueError("Missing or invalid fingerprint")
    if expected.get(subject) != fingerprint:
        raise ValueError("Unexpected ceremony evidence")
    with _transaction(path, plan, True) as (db, digest):
        db.execute("""CREATE TABLE IF NOT EXISTS ceremony_event (
            plan TEXT NOT NULL, event_id TEXT NOT NULL, subject TEXT NOT NULL, fingerprint TEXT NOT NULL,
            PRIMARY KEY(plan, event_id), UNIQUE(plan, subject))""")
        previous = db.execute("SELECT subject, fingerprint FROM ceremony_event WHERE plan=? AND event_id=?",
                              (digest, event_id)).fetchone()
        if subject and not db.execute(
            "SELECT 1 FROM ceremony_event WHERE plan=? AND subject='' AND fingerprint=?",
            (digest, expected[""]),
        ).fetchone():
            raise ValueError("Missing planned CA key event")
        if previous == (subject, fingerprint):
            return
        try:
            db.execute("INSERT INTO ceremony_event VALUES (?, ?, ?, ?)", (digest, event_id, subject, fingerprint))
        except sqlite3.IntegrityError as exc:
            raise ValueError("Conflicting ceremony event") from exc


def readback(path, plan):
    """Return the complete R2 ceremonyLog from one snapshot, or reject it."""
    expected = _expected(plan)
    with _transaction(path, plan, False) as (db, digest):
        rows = db.execute("SELECT subject, fingerprint FROM ceremony_event WHERE plan=? ORDER BY subject",
                          (digest,)).fetchall()
        if dict(rows) != expected or len(rows) != len(expected):
            raise ValueError("Incomplete or conflicting ceremony evidence")
        return {"caKeysCreated": 1, "signed": [
            {"subject": subject, "leafSHA256": fingerprint} for subject, fingerprint in rows if subject
        ]}
