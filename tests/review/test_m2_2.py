"""Missing uncertainty data must not turn a guess into a confirmed shift."""

import extract

from datetime import date


def test_missing_ambiguous_flag_rejects_row(monkeypatch):
    monkeypatch.setattr(
        extract,
        "_gemini",
        lambda *_: '{"shifts": [{"month": 10, "day": 20, "start": "09:00", "end": "17:00", "location": null}]}',
    )

    assert extract.extract(b"schedule", "image/png", "Maria Lopez", date(2026, 10, 18)) == (
        [], ["unreadable"]
    )
