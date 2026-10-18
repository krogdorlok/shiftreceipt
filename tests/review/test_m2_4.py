"""One shift read twice must remain one shift in the schedule."""

from datetime import date

import extract


def test_duplicate_identical_rows_are_collapsed(monkeypatch):
    monkeypatch.setattr(
        extract,
        "_gemini",
        lambda *_: (
            '{"shifts": ['
            '{"month": 10, "day": 20, "start": "09:00", "end": "17:00", "location": "Westwood", "ambiguous": false},'
            '{"month": 10, "day": 20, "start": "09:00", "end": "17:00", "location": "Westwood", "ambiguous": false}'
            ']}'
        ),
    )

    shifts, warnings = extract.extract(b"schedule", "image/png", "Maria Lopez", date(2026, 10, 18))

    assert len(shifts) == 1
    assert warnings == []
