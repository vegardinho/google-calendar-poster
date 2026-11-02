from types import SimpleNamespace
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from calendar_client import CalendarClient
from config import CALENDAR_ID


class FakeLogger:
    def __init__(self):
        self.messages = []

    def info(self, message):
        self.messages.append(("info", message))

    def warning(self, message):
        self.messages.append(("warning", message))


class FakeEvents:
    def __init__(self, pages=None):
        self.pages = iter(pages or [{"items": []}])
        self.calls = []

    def list(self, **kwargs):
        self.calls.append(("list", kwargs))
        page = next(self.pages)
        return SimpleNamespace(execute=lambda: page)

    def insert(self, **kwargs):
        self.calls.append(("insert", kwargs))
        return SimpleNamespace(execute=lambda: {})


def test_list_events_follows_calendar_pages():
    events = FakeEvents(
        [
            {"items": [{"id": "1"}], "nextPageToken": "next"},
            {"items": [{"id": "2"}]},
        ]
    )
    client = CalendarClient(FakeLogger(), SimpleNamespace(events=lambda: events))

    assert client.list_events() == [{"id": "1"}, {"id": "2"}]
    assert events.calls[1][1]["pageToken"] == "next"


def test_post_event_inserts_using_calendar_service():
    logger = FakeLogger()
    events = FakeEvents()
    client = CalendarClient(logger, SimpleNamespace(events=lambda: events))
    event = {
        "id": "42",
        "summary": "Testløp",
        "start": {"date": "2026-11-01"},
    }

    client.post_event(event)

    assert events.calls == [
        (
            "insert",
            {
                "calendarId": (
                    CALENDAR_ID
                ),
                "body": event,
            },
        )
    ]
    assert logger.messages == [("info", 'Upload: "Testløp", 2026-11-01')]
