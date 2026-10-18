"""The Interactions fallback must not add hidden retries beyond M2's one retry."""

from datetime import date
from types import SimpleNamespace

import httpx
from google import genai
from google.genai import types

import extract


def test_interactions_fallback_5xx_has_one_retry(monkeypatch):
    requests = []

    def unavailable(request):
        requests.append(request)
        return httpx.Response(503, json={"error": {"code": 503, "message": "retry", "status": "UNAVAILABLE"}})

    with httpx.Client(transport=httpx.MockTransport(unavailable)) as http:
        real_client = genai.Client(api_key="fake", http_options=types.HttpOptions(httpx_client=http, timeout=20_000))

        def unavailable_primary(**_):
            raise TypeError("generate_content is unavailable")

        client = SimpleNamespace(
            models=SimpleNamespace(generate_content=unavailable_primary),
            interactions=real_client.interactions,
        )
        monkeypatch.setattr(extract.genai, "Client", lambda **_: client)

        assert extract.extract(b"image", "image/png", "Maria Lopez", date(2026, 10, 18)) == (
            [], ["unreadable"]
        )

    assert len(requests) == 2
