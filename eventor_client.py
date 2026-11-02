import logging
import os
import time
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from typing import Any

import requests

from config import EVENTOR_API_KEY_VARIABLE, EVENTOR_API_URL, env_file_path


DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_RETRIES = 3
RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class EventorClient:
    def __init__(
        self,
        api_key: str,
        *,
        session: requests.Session | None = None,
        logger: logging.Logger | None = None,
        retries: int = DEFAULT_RETRIES,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        sleep: Any = time.sleep,
    ) -> None:
        self.api_key = api_key
        self.session: requests.Session = session or requests.Session()
        self.logger: logging.Logger = logger or logging.getLogger(__name__)
        self.retries = retries
        self.timeout = timeout
        self.sleep = sleep

    def get(self, path: str, params: dict[str, str]) -> requests.Response:
        headers = {"Accept": "application/xml, application/json", "ApiKey": self.api_key}
        last_error: requests.RequestException | None = None
        for attempt in range(self.retries + 1):
            try:
                response = self.session.get(
                    EVENTOR_API_URL + path,
                    headers=headers,
                    params=params,
                    timeout=self.timeout,
                )
                if response.status_code not in RETRYABLE_STATUS_CODES:
                    response.raise_for_status()
                    if not response.content.strip():
                        raise RuntimeError(
                            f"Eventor API returned an empty response for {path}"
                        )
                    return response
                error = requests.HTTPError(
                    f"Eventor API returned HTTP {response.status_code} for {path}",
                    response=response,
                )
                last_error = error
            except requests.RequestException as error:
                last_error = error
                if attempt >= self.retries:
                    raise
            if attempt >= self.retries:
                if last_error is not None:
                    raise last_error
                raise RuntimeError(f"Eventor request failed unexpectedly: {path}")
            delay = 2**attempt
            self.logger.warning(
                "Retrying Eventor request %s after attempt %d/%d in %d seconds: %s",
                path,
                attempt + 1,
                self.retries + 1,
                delay,
                last_error,
            )
            self.sleep(delay)
        raise RuntimeError(f"Eventor request failed unexpectedly: {path}")

    def get_documents(self, params: dict[str, str]) -> dict[str, list[tuple[str, str]]]:
        try:
            response = self.get("/events/documents", params)
        except requests.RequestException as error:
            self.logger.warning("Could not load optional Eventor documents: %s", error)
            return {}
        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as error:
            self.logger.warning("Could not parse optional Eventor documents: %s", error)
            return {}

        documents: dict[str, list[tuple[str, str]]] = {}
        for document in root.iter():
            if local_name(document.tag) != "Document":
                continue
            event_id = text(document, "EventId")
            url = first_text(document, "Url", "URL", "Link")
            if event_id and url:
                documents.setdefault(event_id, []).append(
                    (text(document, "Name") or "Eventor document", url)
                )
        return documents

    def iter_events(
        self, response: requests.Response
    ) -> Iterator[tuple[str, ET.Element | dict[str, Any]]]:
        return iter_elements(response)


def load_api_key() -> str:
    key = os.environ.get(EVENTOR_API_KEY_VARIABLE)
    if key:
        return key
    with open(env_file_path(), encoding="utf-8") as env_file:
        for line in env_file:
            name, separator, value = line.partition("=")
            if separator and name.strip() == EVENTOR_API_KEY_VARIABLE:
                key = value.strip().strip("\"'")
                if key:
                    return key
    raise RuntimeError(
        f"{EVENTOR_API_KEY_VARIABLE} is missing; set it in the environment or .env"
    )


def iter_elements(
    response: requests.Response,
) -> Iterator[tuple[str, ET.Element | dict[str, Any]]]:
    try:
        root = ET.fromstring(response.content)
    except ET.ParseError:
        try:
            payload = response.json()
        except ValueError as error:
            raise RuntimeError("Eventor API returned invalid XML and JSON") from error
        if isinstance(payload, list):
            items = payload
        elif isinstance(payload, dict):
            items = payload.get("Events", payload.get("EventList", []))
        else:
            items = []
        return (
            (str(item.get("EventId") or item.get("Id")), item)
            for item in items
        )

    if local_name(root.tag) == "Event":
        elements = (root,)
    else:
        elements = (
            element for element in root
            if local_name(element.tag) == "Event"
        )
    return (
        (text(element, "EventId") or text(element, "Id"), element)
        for element in elements
        if text(element, "EventId") or text(element, "Id")
    )


def first_text(element: ET.Element, *names: str) -> str:
    for name in names:
        value = text(element, name)
        if value:
            return value
    return ""


def text(element: ET.Element, name: str) -> str:
    for node in element.iter():
        if local_name(node.tag) == name and node.text:
            return node.text.strip()
    return ""


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
