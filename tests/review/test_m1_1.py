from uuid import uuid4

import pytest

from agent import DownloadError, download, image_url
from uagents_core.contrib.protocols.chat import Resource, ResourceContent


def test_malformed_resource_uri_uses_valid_metadata_url():
    item = ResourceContent(
        resource_id=uuid4(),
        resource=Resource(uri="http://[bad", metadata={"url": "https://cdn.test/schedule.png"}),
    )
    assert image_url(item) == "https://cdn.test/schedule.png"


def test_malformed_download_url_raises_download_error():
    with pytest.raises(DownloadError):
        download("http://[bad")
