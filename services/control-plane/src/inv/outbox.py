"""At-least-once publication with transactional consumer deduplication."""

from .db import Database


class Outbox:
    def __init__(self, database: Database):
        self.db = database

    def publish_batch(self, tenant_id, publish, *, limit=100):
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("Invalid batch size")
        with self.db.transaction(tenant_id) as conn:
            rows = conn.execute(
                """SELECT event_id,event_type,run_id,payload FROM inv.outbox
                WHERE published_at IS NULL ORDER BY created_at,event_id
                LIMIT %s FOR UPDATE SKIP LOCKED""",
                (limit,),
            ).fetchall()
            for row in rows:
                # A broker ACK followed by a crash can publish twice. Consumers deduplicate.
                publish(
                    {
                        "eventId": str(row["event_id"]),
                        "eventType": row["event_type"],
                        "tenantId": tenant_id,
                        "runId": row["run_id"],
                        "payload": row["payload"],
                    }
                )
                conn.execute(
                    "UPDATE inv.outbox SET published_at=clock_timestamp() WHERE event_id=%s",
                    (row["event_id"],),
                )
            return len(rows)

    def consume(self, tenant_id, consumer, event_id, effect):
        with self.db.transaction(tenant_id) as conn:
            inserted = conn.execute(
                """INSERT INTO inv.consumer_inbox(tenant_id,consumer,event_id)
                VALUES (%s,%s,%s) ON CONFLICT DO NOTHING RETURNING event_id""",
                (tenant_id, consumer, event_id),
            ).fetchone()
            if not inserted:
                return False
            # effect must use this connection for DB effects. External side effects need
            # their own idempotency key/outbox; they cannot be made atomic by this helper.
            effect(conn)
            return True
