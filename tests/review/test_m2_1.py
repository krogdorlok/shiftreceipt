"""A screenshot with no readable schedule must offer the typed fallback."""

import extract

from datetime import date


def test_empty_extraction_is_unreadable(monkeypatch):
    monkeypatch.setattr(extract, "_gemini", lambda *_: '{"shifts": []}')

    assert extract.extract(b"not a schedule", "image/png", "Maria Lopez", date(2026, 10, 18)) == (
        [], ["unreadable"]
    )
