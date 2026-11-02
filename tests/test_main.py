import logging
import sys
from types import ModuleType, SimpleNamespace
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).parents[1]))

email_errors = ModuleType("email_errors")
email_errors.email_errors = lambda *args: None
sys.modules.setdefault("email_errors", email_errors)

my_logger = ModuleType("my_logger")


class FakeLogger:
    def __init__(self, **kwargs):
        pass

    def add_handler(self, **kwargs):
        return self

    def retrieve_logger(self):
        return logging.getLogger("test-post-event-api")


my_logger.MyLogger = FakeLogger
sys.modules.setdefault("my_logger", my_logger)

import config
import eventor_client
import main
import transformer


def response(xml):
    return SimpleNamespace(content=xml.encode())


def event_xml(event_id="42", name="Testløp", finish_date="2026-11-02"):
    return f"""\
<EventList xmlns="urn:eventor">
  <Event>
    <EventId>{event_id}</EventId>
    <Name>{name}</Name>
    <StartDate><Date>2026-11-01</Date><Clock>10:30:00</Clock></StartDate>
    <FinishDate><Date>{finish_date}</Date><Clock>14:00:00</Clock></FinishDate>
  </Event>
</EventList>
"""


def test_iter_elements_reads_top_level_namespaced_events_only():
    events = list(eventor_client.iter_elements(response(event_xml())))

    assert len(events) == 1
    event_id, event = events[0]
    assert event_id == "42"
    assert eventor_client.text(event, "Name") == "Testløp"


def test_event_times_treats_schema_clock_as_local_time():
    event = next(iter(eventor_client.iter_elements(response(event_xml()))))[1]

    start, end = transformer.event_times(event)

    assert start.format("YYYY-MM-DDTHH:mm:ssZZ") == "2026-11-01T10:30:00+01:00"
    assert end.format("YYYY-MM-DDTHH:mm:ssZZ") == "2026-11-02T14:00:00+01:00"


def test_date_only_event_becomes_all_day_calendar_event():
    event = next(
        iter(
            eventor_client.iter_elements(
                response(
                    """\
<EventList xmlns="urn:eventor">
  <Event>
    <EventId>43</EventId>
    <Name>Date-only event</Name>
    <StartDate><Date>2026-11-01</Date></StartDate>
    <FinishDate><Date>2026-11-02</Date></FinishDate>
  </Event>
</EventList>
"""
                )
            )
        )
    )[1]

    packet = transformer.make_packet(event, [])

    assert packet["start"] == {"date": "2026-11-01"}
    assert packet["end"] == {"date": "2026-11-02"}


def test_missing_finish_date_defaults_to_one_day_all_day_event():
    event = next(
        iter(
            eventor_client.iter_elements(
                response(
                    """\
<EventList xmlns="urn:eventor">
  <Event>
    <EventId>44</EventId>
    <Name>Single-day event</Name>
    <StartDate><Date>2026-11-01</Date></StartDate>
  </Event>
</EventList>
"""
                )
            )
        )
    )[1]

    packet = transformer.make_packet(event, [])

    assert packet["start"] == {"date": "2026-11-01"}
    assert packet["end"] == {"date": "2026-11-02"}


def test_missing_location_and_optional_fields_are_omitted():
    event = next(iter(eventor_client.iter_elements(response(event_xml()))))[1]

    packet = transformer.make_packet(event, [])

    assert "location" not in packet
    assert "Organizer:" not in packet["description"]
    assert "Contact:" not in packet["description"]
    assert "Entry deadlines:" not in packet["description"]


def test_missing_start_date_fails_clearly():
    event = next(
        iter(
            eventor_client.iter_elements(
                response(
                    """\
<EventList xmlns="urn:eventor">
  <Event><EventId>45</EventId><Name>Invalid event</Name></Event>
</EventList>
"""
                )
            )
        )
    )[1]

    with pytest.raises(ValueError, match="45.*missing a start time"):
        transformer.event_times(event)


def test_make_packet_contains_eventor_source_and_calendar_times():
    event = next(iter(eventor_client.iter_elements(response(event_xml()))))[1]

    packet = transformer.make_packet(
        event, [("Entry form", "https://example.test/entry")]
    )

    assert packet["id"] == "42"
    assert packet["summary"] == "Testløp"
    assert packet["source"]["url"].endswith("/42")
    assert packet["start"]["dateTime"].startswith("2026-11-01T10:30:00+01:00")
    assert packet["end"]["dateTime"].startswith("2026-11-02T14:00:00+01:00")
    assert "https://example.test/entry" in packet["description"]


@pytest.mark.parametrize(
    ("finish_date", "is_too_long"),
    (("2026-11-08", False), ("2026-11-09", True)),
)
def test_duration_limit_boundary(finish_date, is_too_long):
    event = next(
        iter(
            eventor_client.iter_elements(
                response(event_xml(finish_date=finish_date))
            )
        )
    )[1]
    start, end = transformer.event_times(event)

    assert ((end - start).days > config.MAX_EVENT_DURATION_DAYS) is is_too_long


def test_query_configuration_covers_requested_event_sources():
    assert config.EVENTOR_EVENT_QUERIES == (
        {
            "name": "Championship, national, and international events",
            "classificationIds": "1,2,6",
        },
        {
            "name": "Regional events in Buskerud and Vestfold og Telemark",
            "classificationIds": "3",
            "organisationIds": "5,19",
        },
        {
            "name": "Local events in Vestfold og Telemark",
            "classificationIds": "4",
            "organisationIds": "19",
        },
        {
            "name": "Skien OK club events",
            "classificationIds": "5",
            "organisationIds": "312",
        },
    )


def test_parse_events_updates_matching_event_and_uploads_new_event():
    calls = []

    class Events:
        def insert(self, **kwargs):
            calls.append(("upload", kwargs))
            return self

        def update(self, **kwargs):
            calls.append(("update", kwargs))
            return self

        def delete(self, **kwargs):
            calls.append(("delete", kwargs))
            return self

        def execute(self):
            return {}

    service = SimpleNamespace(events=lambda: Events())
    existing = {
        "id": "42",
        "summary": "Old name",
        "start": {"date": "2026-11-01"},
        "status": "confirmed",
    }
    new = {
        "id": "42",
        "summary": "New name",
        "start": {"date": "2026-11-01"},
        "end": {"date": "2026-11-02"},
        "description": "",
    }
    uploaded = {
        "id": "99",
        "summary": "Removed",
        "start": {"date": "2026-11-03"},
        "status": "confirmed",
    }

    main.parse_events(service, [new], [existing, uploaded])

    assert [call[0] for call in calls] == ["update", "delete"]


def test_post_event_propagates_calendar_failures_without_email_side_effect():
    class FailingEvents:
        def insert(self, **kwargs):
            raise RuntimeError("calendar unavailable")

    service = SimpleNamespace(events=lambda: FailingEvents())
    event = {
        "id": "42",
        "summary": "Testløp",
        "start": {"date": "2026-11-01"},
    }

    with pytest.raises(RuntimeError, match="calendar unavailable"):
        main.post_event(service, event)
