import os
import pickle
import re
import logging
from typing import Any

from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow

from config import (
    CALENDAR_ID,
    END_DATE,
    GOOGLE_CREDENTIALS_FILE,
    GOOGLE_TOKEN_FILE,
    START_DATE,
    T_FORMAT,
)
from models import CalendarEvent


class CalendarClient:
    def __init__(
        self, logger: logging.Logger, service: Any = None
    ) -> None:
        self._logger = logger
        self._service = service

    @classmethod
    def connect(cls, logger: logging.Logger) -> "CalendarClient":
        """Authenticate with Google and return a connected Calendar client."""
        logger.info("Setting up connection")
        scopes = ["https://www.googleapis.com/auth/calendar"]
        creds = None

        # Reuse the token when possible; interactive authorization is only
        # needed for the first run or after an unusable token.
        if os.path.exists(GOOGLE_TOKEN_FILE) and os.path.getsize(GOOGLE_TOKEN_FILE) > 0:
            with open(GOOGLE_TOKEN_FILE, "rb") as token:
                creds = pickle.load(token)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    GOOGLE_CREDENTIALS_FILE, scopes
                )
                creds = flow.run_local_server(port=0)
            os.makedirs(os.path.dirname(GOOGLE_TOKEN_FILE), exist_ok=True)
            with open(GOOGLE_TOKEN_FILE, "wb") as token:
                pickle.dump(creds, token)

        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        return cls(logger, service)

    @property
    def service(self) -> Any:
        """Return the Google API service, failing if authentication is incomplete."""
        if self._service is None:
            raise RuntimeError("Calendar client is not connected")
        return self._service

    def list_events(self) -> list[dict[str, object]]:
        """Fetch all configured-calendar events across every result page."""
        tmax = END_DATE.format(T_FORMAT)
        tmin = START_DATE.format(T_FORMAT)
        events = []
        page_token = None
        while True:
            # Google Calendar paginates results, so continue until no token is returned.
            response = self.service.events().list(
                calendarId=CALENDAR_ID,
                pageToken=page_token,
                timeMin=tmin,
                timeMax=tmax,
                showDeleted=True,
            ).execute()
            events.extend(response["items"])
            page_token = response.get("nextPageToken")
            if not page_token:
                return events

    def post_event(
        self, event: CalendarEvent, action: str = "upload"
    ) -> None:
        """Upload, update, or delete one event in Google Calendar."""
        start_date = re.search(r"\d{4}.\d{2}.\d{2}", str(event["start"])).group()
        self._logger.info(f'{action.capitalize()}: "{event["summary"]}", {start_date}')

        try:
            # A conflict means an event with this ID already exists; updating it
            # keeps synchronization idempotent.
            if action == "upload":
                self.service.events().insert(
                    calendarId=CALENDAR_ID, body=event
                ).execute()
            elif action == "update":
                self.service.events().update(
                    calendarId=CALENDAR_ID, eventId=event["id"], body=event
                ).execute()
            elif action == "delete":
                self.service.events().delete(
                    calendarId=CALENDAR_ID, eventId=event["id"]
                ).execute()
            else:
                raise ValueError(
                    f"Wrong parameter value [upload|update|delete]: {action}"
                )
        except HttpError as err:
            if err.resp.status == 409 and action == "upload":
                self._logger.warning(err)
                self._logger.warning("Attempting to repost by update")
                self.post_event(event, "update")
            else:
                raise
