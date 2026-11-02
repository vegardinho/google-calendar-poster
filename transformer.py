import logging
import re
import xml.etree.ElementTree as ET
from datetime import timedelta
from collections.abc import Iterator
from typing import Any

import arrow
from arrow import Arrow

from config import (
    D_FORMAT,
    EVENTOR_EVENT_URL,
    MAX_EVENT_DURATION_DAYS,
    T_FORMAT,
    TIMEZONE,
)
from eventor_client import local_name, text
from models import CalendarEvent


def make_packet(event: Any, documents: list[tuple[str, str]]) -> CalendarEvent:
    event_id = first_text(event, "EventId", "Id")
    name = first_text(event, "Name") or f"Event {event_id}"
    start, end = event_times(event)
    event_url = EVENTOR_EVENT_URL.format(event_id)
    description_parts = []

    for label, value in (
        ("Status", nested_name(event, "EventStatus")),
        ("Organizer", nested_name(event, "Organiser")),
        ("Entry deadlines", entry_deadlines(event)),
        ("Contact", contact_details(event)),
    ):
        if value:
            description_parts.append(f"{label}: {value}")
    description_parts.extend(f"{name}: {url}" for name, url in documents)
    description_parts.append(
        f'See <a href="{event_url}" target="_blank">{event_url}</a>'
    )

    packet: CalendarEvent = {
        "summary": name,
        "source": {"title": "Eventor-arrangement", "url": event_url},
        "id": str(event_id),
        "description": "\n\n".join(description_parts),
        "start": get_time_format(start, end)[0],
        "end": get_time_format(start, end)[1],
    }
    location = location_details(event)
    if location:
        packet["location"] = location
    return packet


def should_include_event(
    event: Any,
    *,
    logger: logging.Logger,
    max_duration_days: int = MAX_EVENT_DURATION_DAYS,
) -> bool:
    event_id = first_text(event, "EventId", "Id")
    name = first_text(event, "Name") or f"Event {event_id}"
    start, end = event_times(event)
    duration = end - start
    if duration > timedelta(days=max_duration_days):
        logger.info(
            'Skipping event "%s" (%s): duration %.1f days exceeds '
            "maximum of %d days",
            name,
            event_id,
            duration.total_seconds() / 86400,
            max_duration_days,
        )
        return False
    return True


def parse_event_time(value: str | None) -> Arrow | None:
    if not value:
        return None
    parsed = arrow.get(value)
    if re.search(r"(?:Z|[+-]\d{2}:\d{2})$", value):
        return parsed.to(TIMEZONE)
    return parsed.replace(tzinfo=TIMEZONE)


def event_times(event: Any) -> tuple[Arrow, Arrow]:
    event_id = first_text(event, "EventId", "Id")
    start = parse_event_time(event_date(event, "StartDate"))
    if start is None:
        raise ValueError(f"Eventor event {event_id} is missing a start time")
    end = parse_event_time(event_date(event, "FinishDate"))
    if end is None:
        end = start.shift(days=1) if start.hour == 0 else start.shift(hours=4)
    return start, end


def event_date(event: Any, name: str) -> str:
    if isinstance(event, dict):
        value = event.get(name, "")
        if isinstance(value, dict):
            date = str(value.get("Date", ""))
            clock = str(value.get("Clock", ""))
            return f"{date}T{clock}" if date and clock else date
        return str(value)
    date_node = next(iter(descendants(event, name)), None)
    if date_node is None:
        return ""
    date = text(date_node, "Date")
    clock = text(date_node, "Clock")
    if date and clock:
        return f"{date}T{clock}"
    return date


def get_time_format(start: Arrow | None, end: Arrow | None) -> list[dict[str, str]]:
    if start is None or end is None:
        raise ValueError("Eventor event is missing a start or end time")
    if start.hour == end.hour == 0:
        return [{"date": start.format(D_FORMAT)}, {"date": end.format(D_FORMAT)}]
    return [
        {"dateTime": start.format(T_FORMAT), "timeZone": TIMEZONE},
        {"dateTime": end.format(T_FORMAT), "timeZone": TIMEZONE},
    ]


def first_text(element: Any, *names: str) -> str:
    for name in names:
        value = text(element, name)
        if value:
            return value
    return ""


def nested_name(event: Any, name: str) -> str:
    if isinstance(event, dict):
        value = event.get(name, {})
        return str(value.get("Name", "")) if isinstance(value, dict) else ""
    node = next(iter(descendants(event, name)), None)
    return text(node, "Name") if node is not None else ""


def entry_deadlines(event: Any) -> str:
    return ", ".join(
        value
        for node in descendants(event, "EntryBreak")
        if (
            value := ", ".join(
                date
                for date in (
                    event_date(node, "ValidFromDate"),
                    event_date(node, "ValidToDate"),
                )
                if date
            )
        )
    )


def contact_details(event: Any) -> str:
    contact = next(iter(descendants(event, "ContactData")), None)
    if contact is None:
        return ""
    values = []
    for node in descendants(contact, "Address", "Tele"):
        values.extend(
            value
            for value in (
                node.attrib.get("street"),
                node.attrib.get("city"),
                node.attrib.get("zipCode"),
                node.attrib.get("phoneNumber"),
                node.attrib.get("mobilePhoneNumber"),
                node.attrib.get("mailAddress"),
            )
            if value
        )
    return ", ".join(values)


def location_details(event: Any) -> str:
    position = next(iter(descendants(event, "EventCenterPosition")), None)
    if position is None:
        return ""
    x = position.attrib.get("x")
    y = position.attrib.get("y")
    if not x or not y:
        return ""
    values = [f"{x}, {y}"]
    unit = position.attrib.get("unit")
    if unit:
        values.append(unit)
    return ", ".join(dict.fromkeys(values))


def descendants(element: Any, *names: str) -> Iterator[ET.Element]:
    wanted = set(names)
    if isinstance(element, dict):
        return ()
    return (node for node in element.iter() if local_name(node.tag) in wanted)
