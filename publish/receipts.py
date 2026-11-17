"""Recibos duráveis, inclusive para respostas perdidas e conferência do operador."""

import json
from datetime import datetime, timezone

from publish.errors import PublishError


class UncertainDelivery(PublishError):
    pass


def ensure(db):
    db.conn.execute("""CREATE TABLE IF NOT EXISTS publish_receipts (
        job_id INTEGER PRIMARY KEY, platform TEXT NOT NULL, remote_id TEXT NOT NULL DEFAULT '',
        state TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL)""")


def save(db, job_id, platform, state, remote_id="", note=""):
    ensure(db)
    db.conn.execute("""INSERT INTO publish_receipts VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(job_id) DO UPDATE SET remote_id=CASE WHEN excluded.remote_id != ''
        THEN excluded.remote_id ELSE publish_receipts.remote_id END,
        state=excluded.state, note=excluded.note, updated_at=excluded.updated_at""",
        (job_id, platform, remote_id, state, note[:500], datetime.now(timezone.utc).isoformat()))
    db.conn.commit()


def get(db, job_id):
    ensure(db)
    row = db.conn.execute("SELECT * FROM publish_receipts WHERE job_id=?", (job_id,)).fetchone()
    return dict(row) if row else {}


def require_reconciled(db, clip_id, platform):
    """A retry never infers absence from a timeout, restart or HTTP failure."""
    ensure(db)
    rows = db.conn.execute("SELECT * FROM publish_jobs WHERE clip_id=? ORDER BY id DESC", (clip_id,))
    for row in rows:
        request = json.loads(row["request"])
        if request.get("provider") != "composio" or request.get("platform") != platform:
            continue
        receipt = get(db, row["id"])
        if receipt.get("state") == "confirmed_absent":
            continue
        if row["status"] not in ("failed", "cancelled") or receipt.get("state") in ("submitting", "uncertain", "accepted", "awaiting_operator", "published"):
            raise PublishError("Confira e reconcilie o envio anterior antes de repetir este corte.")
