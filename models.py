from typing import NotRequired, TypedDict


class EventQuery(TypedDict):
    name: str
    classificationIds: str
    organisationIds: NotRequired[str]


class CalendarDate(TypedDict):
    date: NotRequired[str]
    dateTime: NotRequired[str]
    timeZone: NotRequired[str]


class CalendarSource(TypedDict):
    title: str
    url: str


class CalendarEvent(TypedDict):
    id: str
    summary: str
    source: CalendarSource
    description: str
    start: CalendarDate
    end: CalendarDate
    location: NotRequired[str]
