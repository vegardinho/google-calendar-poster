import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from application import run, run_with_error_reporting


class FakeLogger:
    def __init__(self):
        self.messages = []

    def info(self, message):
        self.messages.append(("info", message))

    def exception(self, message):
        self.messages.append(("exception", message))


def test_run_orchestrates_calendar_fetch_and_sync():
    calls = []
    logger = FakeLogger()

    def setup():
        calls.append("setup")
        return "calendar"

    def get_events():
        calls.append("get_events")
        return ["new"]

    def get_uploaded_events(calendar):
        calls.append(("get_uploaded_events", calendar))
        return ["old"]

    def parse_events(calendar, new_events, uploaded_events, dry_run):
        calls.append(("parse_events", calendar, new_events, uploaded_events, dry_run))

    run(logger, setup, get_events, get_uploaded_events, parse_events)

    assert calls == [
        "setup",
        "get_events",
        ("get_uploaded_events", "calendar"),
        ("parse_events", "calendar", ["new"], ["old"], False),
    ]
    assert logger.messages == [("info", "LOG START")]


def test_run_with_error_reporting_reports_failure_and_does_not_hide_it():
    logger = FakeLogger()
    emails = []

    def main():
        raise RuntimeError("failed")

    run_with_error_reporting(
        logger,
        main,
        lambda *args: emails.append(args),
        "recipient@example.test",
        "errors.out",
        "info.log",
        "main.py",
    )

    assert logger.messages == [("exception", "Run failed")]
    assert len(emails) == 1
    assert isinstance(emails[0][0], RuntimeError)
    assert emails[0][1:] == (
        "recipient@example.test",
        str(Path.cwd() / "main.py"),
        "errors.out",
        logger,
        "info.log",
    )


def test_run_with_error_reporting_resets_error_history_on_success():
    logger = FakeLogger()
    emails = []

    run_with_error_reporting(
        logger,
        lambda: None,
        lambda *args: emails.append(args),
        "recipient@example.test",
        "errors.out",
        "info.log",
        "main.py",
    )

    assert emails[0][0] is None
