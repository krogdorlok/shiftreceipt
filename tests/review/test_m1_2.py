import httpx
import pytest

from agent import MAX_BYTES, DownloadError, download


def test_download_rejects_empty_image_body():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, headers={"content-type": "image/png"}, content=b"")
    )
    with pytest.raises(DownloadError):
        download("https://cdn.test/empty.png", transport)


def test_download_caps_redirect_body():
    def respond(request):
        if request.url.path == "/redirect":
            return httpx.Response(
                302,
                headers={"location": "/schedule.png"},
                stream=httpx.ByteStream(b"x" * (MAX_BYTES + 1)),
            )
        return httpx.Response(200, headers={"content-type": "image/png"}, content=b"png")

    with pytest.raises(DownloadError, match="too large"):
        download("https://cdn.test/redirect", httpx.MockTransport(respond))
