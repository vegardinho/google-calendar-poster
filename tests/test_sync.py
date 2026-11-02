import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from sync import synchronize


class FakeLogger:
    def __init__(self):
        self.messages = []

    def info(self, message):
        self.messages.append(("info", message))

    def debug(self, message):
        self.messages.append(("debug", message))

    def warning(self, message):
        self.messages.append(("warning", message))


class FakeCalendar:
    def __init__(self):
        self.calls = []

    def post_event(self, event, action):
        self.calls.append((action, event["id"]))


def test_synchronize_updates_changed_events_deletes_removed_and_uploads_new():
    calendar = FakeCalendar()
    logger = FakeLogger()
    uploaded = [
        {
            "id": "changed",
            "summary": "Old",
            "start": {"date": "2026-11-01"},
            "status": "confirmed",
        },
        {
            "id": "removed",
            "summary": "Removed",
            "start": {"date": "2026-11-02"},
            "status": "confirmed",
        },
    ]
    new = [
        {"id": "changed", "summary": "New", "start": {"date": "2026-11-01"}},
        {"id": "added", "summary": "Added", "start": {"date": "2026-11-03"}},
    ]

    synchronize(calendar, new, uploaded, logger)

    assert calendar.calls == [
        ("update", "changed"),
        ("delete", "removed"),
        ("upload", "added"),
    ]


def test_synchronize_updates_cancelled_matching_event():
    calendar = FakeCalendar()
    logger = FakeLogger()
    uploaded = [
        {
            "id": "42",
            "summary": "Same",
            "start": {"date": "2026-11-01"},
            "status": "cancelled",
        }
    ]
    new = [{"id": "42", "summary": "Same", "start": {"date": "2026-11-01"}}]

    synchronize(calendar, new, uploaded, logger)

    assert calendar.calls == [("update", "42")]


def test_synchronize_dry_run_logs_changes_without_modifying_calendar():
    calendar = FakeCalendar()
    logger = FakeLogger()
    uploaded = [
        {
            "id": "removed",
            "summary": "Removed",
            "start": {"date": "2026-11-01"},
            "status": "confirmed",
        }
    ]
    new = [{"id": "added", "summary": "Added", "start": {"date": "2026-11-02"}}]

    synchronize(calendar, new, uploaded, logger, dry_run=True)

    assert calendar.calls == []
    assert logger.messages[-2:] == [
        ("info", '[dry-run] Would delete event "Removed" (removed)'),
        ("info", '[dry-run] Would upload event "Added" (added)'),
    ]
