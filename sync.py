import logging
from collections.abc import Sequence
from typing import Any

from models import CalendarEvent


def synchronize(
    calendar: Any,
    new_events: Sequence[CalendarEvent],
    uploaded_events: Sequence[dict[str, object]],
    logger: logging.Logger,
    dry_run: bool = False,
) -> None:
    """Update changed events, remove stale ones, and upload new events."""
    logger.info("Parsing events")
    ignore_events = []
    for new_event in new_events:
        for uploaded_event in uploaded_events:
            if new_event["id"] == uploaded_event["id"]:
                # Matching IDs identify the same calendar event; compare the
                # payload fields to detect changes from Eventor.
                logger.debug(
                    'Event "{}" ({}) found in previously uploaded events'.format(
                        new_event["summary"], new_event["start"]
                    )
                )
                for field in new_event:
                    try:
                        if (
                            new_event[field] != uploaded_event[field]
                            or uploaded_event["status"] == "cancelled"
                        ):
                            logger.debug(
                                'Event "{}" has changed!'.format(new_event["summary"])
                            )
                            _post_event(
                                calendar, new_event, "update", logger, dry_run
                            )
                            break
                    except KeyError as err:
                        logger.warning(
                            f"Tag does not exist: {err} ({new_event['summary']}"
                        )
                ignore_events.extend((uploaded_event, new_event))
                break

    # Anything previously uploaded but absent from Eventor is stale and should
    # be removed, except events already marked cancelled by Calendar.
    for old_event in uploaded_events:
        if old_event not in ignore_events and old_event["status"] != "cancelled":
            _post_event(calendar, old_event, "delete", logger, dry_run)
    # Remaining Eventor events have never been uploaded and are new.
    for new_event in new_events:
        if new_event not in ignore_events:
            _post_event(calendar, new_event, "upload", logger, dry_run)


def _post_event(
    calendar: Any,
    event: CalendarEvent | dict[str, object],
    action: str,
    logger: logging.Logger,
    dry_run: bool,
) -> None:
    """Apply one calendar action, or describe it without mutation in dry-run mode."""
    if dry_run:
        # Dry-run must describe every mutation without calling the Calendar API.
        logger.info(
            f'[dry-run] Would {action} event "{event["summary"]}" '
            f'({event["id"]})'
        )
        return
    calendar.post_event(event, action)
