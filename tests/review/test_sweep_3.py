from datetime import datetime, timedelta

import db
from models import LA


def test_notice_limit_counts_send_day_not_creation_day(tmp_path):
    path = str(tmp_path / "cap.db")
    db.init(path)
    yesterday = (datetime.now(LA) - timedelta(days=1)).isoformat()
    old = db.create_notice(path, "worker", [], 100)
    with db.conn(path) as c:
        c.execute("UPDATE notices SET created_at=? WHERE id=?", (yesterday, old))
    assert db.claim_notice(path, "worker", old)
    db.finish_notice(path, "worker", old, "<old>")
    second = db.create_notice(path, "worker", [], 100)
    assert db.claim_notice(path, "worker", second)
    db.finish_notice(path, "worker", second, "<second>")
    third = db.create_notice(path, "worker", [], 100)
    assert db.claim_notice(path, "worker", third) is False
