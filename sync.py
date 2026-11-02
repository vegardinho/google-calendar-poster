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
    logger.info("Parsing events")
    ignore_events = []
    for new_event in new_events:
        for uploaded_event in uploaded_events:
            if new_event["id"] == uploaded_event["id"]:
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

    for old_event in uploaded_events:
        if old_event not in ignore_events and old_event["status"] != "cancelled":
            _post_event(calendar, old_event, "delete", logger, dry_run)
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
    if dry_run:
        logger.info(
            f'[dry-run] Would {action} event "{event["summary"]}" '
            f'({event["id"]})'
        )
        return
    calendar.post_event(event, action)
