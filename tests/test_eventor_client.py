import logging
import sys
from types import SimpleNamespace
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).parents[1]))

from eventor_client import EventorClient, iter_elements


def test_iter_elements_supports_json_event_lists():
    response = SimpleNamespace(
        content=b"not xml",
        json=lambda: {"EventList": [{"EventId": 7, "Name": "Test"}]},
    )

    events = list(iter_elements(response))

    assert events == [("7", {"EventId": 7, "Name": "Test"})]


def test_iter_elements_rejects_invalid_xml_and_json():
    response = SimpleNamespace(
        content=b"not xml",
        json=lambda: (_ for _ in ()).throw(ValueError("invalid json")),
    )

    with pytest.raises(RuntimeError, match="invalid XML and JSON"):
        list(iter_elements(response))


def test_get_retries_transient_http_errors():
    failed = requests.Response()
    failed.status_code = 503
    failed._content = b"busy"
    success = requests.Response()
    success.status_code = 200
    success._content = b"<EventList />"
    responses = [failed, success]

    class Session:
        def get(self, *args, **kwargs):
            return responses.pop(0)

    delays = []
    client = EventorClient(
        "key",
        session=Session(),
        logger=logging.getLogger("test-eventor-client"),
        sleep=delays.append,
    )

    response = client.get("/events", {})

    assert response.status_code == 200
    assert delays == [1]


def test_get_raises_after_retry_limit():
    class Session:
        def get(self, *args, **kwargs):
            raise requests.Timeout("timed out")

    client = EventorClient("key", session=Session(), retries=2, sleep=lambda _: None)

    with pytest.raises(requests.Timeout):
        client.get("/events", {})
