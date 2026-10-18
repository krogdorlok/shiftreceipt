"""The installed Interactions SDK requires the response MIME type beside its schema."""

from types import SimpleNamespace

import extract


def test_interactions_fallback_declares_json_response_mime(monkeypatch):
    def generate_content(**_):
        raise TypeError("generate_content signature unavailable")

    def create(**kwargs):
        assert kwargs["response_mime_type"] == "application/json"
        return SimpleNamespace(output_text='{"shifts": []}')

    client = SimpleNamespace(
        models=SimpleNamespace(generate_content=generate_content),
        interactions=SimpleNamespace(create=create),
    )
    monkeypatch.setattr(extract.genai, "Client", lambda **_: client)

    assert extract._gemini(b"image", "image/png", "prompt") == '{"shifts": []}'
