from uuid import uuid4

import httpx
import pytest

from agent import FALLBACK_TEXT, HELP_TEXT, SCHEDULE_EXAMPLE, DownloadError, download, image_url
from parser import parse
from uagents_core.contrib.protocols.chat import Resource, ResourceContent

PNG = b"\x89PNG" + b"0" * 2048


def T(handler):
    return httpx.MockTransport(handler)


def ok(req):
    return httpx.Response(200, headers={"content-type": "image/png"}, content=PNG)


def test_download_ok():
    assert download("https://x.test/a.png?sig=1", T(ok)) == (PNG, "image/png")


def test_download_follows_redirect():
    def h(req):
        return ok(req) if req.url.path == "/b" else httpx.Response(302, headers={"location": "/b"})
    assert download("http://x.test/a", T(h))[0] == PNG


def test_download_timeout():
    def h(req):
        raise httpx.ReadTimeout("slow", request=req)
    with pytest.raises(DownloadError, match="timeout"):
        download("https://x.test/a.png", T(h))


def test_download_11mb_with_length():
    big = b"0" * (11 * 1024 * 1024)
    with pytest.raises(DownloadError, match="too large"):
        download("https://x.test/a.png", T(lambda r: httpx.Response(200, headers={"content-type": "image/png"},
                                                                   content=big)))


def test_download_11mb_streamed_without_length():
    chunks = (b"0" * (1024 * 1024) for _ in range(11))
    with pytest.raises(DownloadError, match="too large"):
        download("https://x.test/a.png", T(lambda r: httpx.Response(200, headers={"content-type": "image/png"},
                                                                   stream=httpx.ByteStream(b"".join(chunks)))))


def test_download_html_rejected():
    with pytest.raises(DownloadError, match="not an image"):
        download("https://x.test/a", T(lambda r: httpx.Response(200, headers={"content-type": "text/html"},
                                                               content=b"<html>")))


def test_download_ftp_rejected_without_request():
    def h(req):
        raise AssertionError("must not request")
    for url in ("ftp://x.test/a.png", "file:///etc/passwd", "x.test/a.png", ""):
        with pytest.raises(DownloadError):
            download(url, T(h))


def test_download_404():
    with pytest.raises(DownloadError, match="404"):
        download("https://x.test/a.png", T(lambda r: httpx.Response(404)))


def test_download_error_never_contains_url():
    def h(req):
        raise httpx.ConnectError("boom https://x.test/a.png?token=secret", request=req)
    with pytest.raises(DownloadError) as e:
        download("https://x.test/a.png?token=secret", T(h))
    assert "secret" not in str(e.value)


def RC(*resources):
    return ResourceContent(resource_id=uuid4(), resource=list(resources) if len(resources) > 1 else resources[0])


def test_image_url_from_uri():
    assert image_url(RC(Resource(uri="https://cdn.test/a.png", metadata={}))) == "https://cdn.test/a.png"


@pytest.mark.parametrize("key", ["url", "uri", "source", "image_url"])
def test_image_url_from_metadata(key):
    assert image_url(RC(Resource(uri="agent-storage://abc", metadata={key: "http://cdn.test/b.png"}))) == \
        "http://cdn.test/b.png"


def test_image_url_list_of_resources():
    rc = RC(Resource(uri="agent-storage://abc", metadata={"mime_type": "image/png"}),
            Resource(uri="https://cdn.test/c.png", metadata={}))
    assert image_url(rc) == "https://cdn.test/c.png"


def test_image_url_non_http():
    assert image_url(RC(Resource(uri="ftp://cdn.test/a.png", metadata={"url": "data:image/png;base64,AA"}))) is None


def test_texts():
    assert parse(SCHEDULE_EXAMPLE.strip("`\n")).name == "SCHEDULE"
    for t in (HELP_TEXT, FALLBACK_TEXT):
        assert "—" not in t and "you are owed" not in t.lower()
    assert "Not legal advice" in HELP_TEXT and "may be owed" in HELP_TEXT


def test_redirect_loop_and_bad_redirect():
    with pytest.raises(DownloadError, match="too many"):
        download("https://x.test/a", T(lambda r: httpx.Response(302, headers={"location": "/a"})))
    with pytest.raises(DownloadError):
        download("https://x.test/a", T(lambda r: httpx.Response(302, headers={"location": "ftp://x.test/a.png"})))
