#!/usr/bin/env python3

import argparse
import logging
from functools import partial
from typing import Any

from python_tools.email_errors import email_errors
from python_tools.my_logger import MyLogger

from application import run, run_with_error_reporting
from calendar_client import CalendarClient
from config import (
    DEBUG_LOG_FILE,
    EMAIL_ERR_FILE,
    EMAIL_PASSWORD_FILE,
    END_DATE,
    ERR_EMAIL,
    ERR_LOG_FILE,
    EVENTOR_EVENT_QUERIES,
    INFO_LOG_FILE,
    START_DATE,
)
from eventor_client import EventorClient, load_api_key
from models import CalendarEvent
from sync import synchronize
from transformer import make_packet, should_include_event


def retrieve_logger() -> logging.Logger:
    """Configure and return the application's console and file logger."""
    log_obj = MyLogger(logger_name="google_calendar_poster")
    log_obj.add_handler(level="INFO")
    log_obj.add_handler(level="DEBUG", filename=DEBUG_LOG_FILE, max_log_files=3)
    log_obj.add_handler(level="INFO", filename=INFO_LOG_FILE)
    log_obj.add_handler(level="ERROR", filename=ERR_LOG_FILE)
    return log_obj.retrieve_logger()


log = retrieve_logger()


def main(dry_run: bool = False) -> None:
    """Run one synchronization cycle, optionally without calendar mutations."""
    # Keep orchestration independent from command-line parsing for testability.
    run(log, setup, get_events, get_uploaded_events, parse_events, dry_run)


def post_event(service: Any, event: CalendarEvent, action: str = "upload") -> None:
    """Post one event through either a client or a raw Google service."""
    _calendar_client(service).post_event(event, action)


def parse_events(
    service: Any,
    new_events: list[CalendarEvent],
    uploaded_events: list[dict[str, object]],
    dry_run: bool = False,
) -> None:
    """Reconcile fetched Eventor events with events already in Calendar."""
    synchronize(_calendar_client(service), new_events, uploaded_events, log, dry_run)


def setup() -> CalendarClient:
    """Create the authenticated Google Calendar client."""
    return CalendarClient.connect(log)


def get_events() -> list[CalendarEvent]:
    """Fetch, filter, deduplicate, and transform Eventor events."""
    api_key = load_api_key()
    client = EventorClient(api_key, logger=log)
    date_params = {
        "fromDate": START_DATE.format("YYYY-MM-DD HH:mm:ss"),
        "toDate": END_DATE.format("YYYY-MM-DD HH:mm:ss"),
        "includeEntryBreaks": "true",
        "includeAttributes": "true",
    }

    events_by_id = {}
    documents_by_event_id = {}
    for query in EVENTOR_EVENT_QUERIES:
        # Several queries intentionally overlap; retain the first occurrence
        # so each Eventor event is synchronized only once.
        params = {**date_params, **query}
        params.pop("name", None)
        log.info("Loading Eventor query: %s", query["name"])
        events_response = client.get("/events", params)
        documents = client.get_documents(params)
        documents_by_event_id.update(documents)
        for event_id, event in client.iter_events(events_response):
            if not should_include_event(event, logger=log):
                continue
            events_by_id.setdefault(event_id, event)

    # Convert only after all queries are merged, so document lookups and
    # deduplication are completed before calendar payloads are built.
    events = [
        make_packet(event, documents_by_event_id.get(event_id, []))
        for event_id, event in events_by_id.items()
    ]
    events.sort(key=lambda event: event["id"])
    log.info("Loaded %d events from Eventor API", len(events))
    return events


def get_uploaded_events(service: Any) -> list[dict[str, object]]:
    """Retrieve existing calendar events through the supported service shape."""
    if isinstance(service, CalendarClient):
        return service.list_events()
    return _calendar_client(service).list_events()


def _calendar_client(service: Any) -> CalendarClient:
    """Normalize a client or raw service into a CalendarClient instance."""
    if isinstance(service, CalendarClient):
        return service
    return CalendarClient(log, service)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List synchronization changes without modifying Google Calendar.",
    )
    args = parser.parse_args()
    run_with_error_reporting(
        log,
        lambda: main(args.dry_run),
        partial(email_errors, pwd_file=EMAIL_PASSWORD_FILE),
        ERR_EMAIL,
        EMAIL_ERR_FILE,
        INFO_LOG_FILE,
        __file__,
    )
