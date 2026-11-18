"""Local, synthetic A1 evidence for an independently validated R2 plan."""
from contextlib import closing, contextmanager
from pathlib import Path
import re
import sqlite3

from tools.check_fleet5_authority_replacement_r2 import ceremony_outputs, digest, plan_digest, validate_plan


def _expected(plan):
    # Reviewed public p02 fixture. R2 deliberately excludes ceremony outputs from plan_digest.
    binding = {"planDigest": plan_digest(plan), "outputs": ceremony_outputs(plan)}
    if digest(binding) != "4f04475ca2f6844b46b824657ab087dea484a37a447b6793214711c62441a7de" or validate_plan(plan):
        raise ValueError("Unreviewed or invalid R2 ceremony plan")
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
    if not isinstance(subject, str):
        raise ValueError("Invalid subject")
    with _transaction(path, plan, True) as (db, digest):
        tables = {row[0] for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('ceremony_event','ceremony_conflict')"
        )}
        if tables and len(tables) != 2:
            raise ValueError("Legacy or incomplete ledger requires independent reconciliation")
        db.execute("""CREATE TABLE IF NOT EXISTS ceremony_event (
            plan TEXT NOT NULL, event_id TEXT NOT NULL, subject TEXT NOT NULL, fingerprint TEXT NOT NULL,
            PRIMARY KEY(plan, event_id), UNIQUE(plan, subject))""")
        db.execute("""CREATE TABLE IF NOT EXISTS ceremony_conflict (
            plan TEXT NOT NULL, event_id TEXT NOT NULL, subject TEXT NOT NULL, fingerprint TEXT NOT NULL,
            PRIMARY KEY(plan, event_id, subject, fingerprint))""")
        previous = db.execute("SELECT subject, fingerprint FROM ceremony_event WHERE plan=? AND event_id=?",
                              (digest, event_id)).fetchone()
        if previous == (subject, fingerprint):
            return
        ca_present = db.execute("SELECT 1 FROM ceremony_event WHERE plan=? AND subject='' AND fingerprint=?",
                                (digest, expected[""])).fetchone()
        if expected.get(subject) == fingerprint and (not subject or ca_present):
            inserted = db.execute("INSERT OR IGNORE INTO ceremony_event VALUES (?, ?, ?, ?)",
                                  (digest, event_id, subject, fingerprint))
            if inserted.rowcount:
                return
        db.execute("INSERT OR IGNORE INTO ceremony_conflict VALUES (?, ?, ?, ?)",
                   (digest, event_id, subject, fingerprint))
    # Surface the conflict only after its transaction commits.
    raise ValueError("Conflicting ceremony event")


def readback(path, plan):
    """Return the complete R2 ceremonyLog from one snapshot, or reject it."""
    expected = _expected(plan)
    with _transaction(path, plan, False) as (db, digest):
        rows = db.execute("SELECT subject, fingerprint FROM ceremony_event WHERE plan=? ORDER BY subject",
                          (digest,)).fetchall()
        conflict = db.execute("SELECT 1 FROM ceremony_conflict WHERE plan=? LIMIT 1", (digest,)).fetchone()
        if conflict or dict(rows) != expected or len(rows) != len(expected):
            raise ValueError("Incomplete or conflicting ceremony evidence")
        return {"caKeysCreated": 1, "signed": [
            {"subject": subject, "leafSHA256": fingerprint} for subject, fingerprint in rows if subject
        ]}
