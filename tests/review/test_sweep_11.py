"""The standalone receipt card needs the required legal note beside its amount."""
import json

import agent


def test_amount_on_card_has_legal_note(monkeypatch):
    monkeypatch.setattr(agent, "CARDS", True)
    card = agent._card(7, 7000, "boss@example.com")
    assert card is not None
    payload = json.loads(card.metadata["card_payload"])
    assert "Not legal advice" in json.dumps(payload)
