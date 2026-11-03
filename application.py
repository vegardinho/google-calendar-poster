import atexit
import os
import logging
from collections.abc import Callable, Sequence
from typing import Any

from models import CalendarEvent


def run(
    log: logging.Logger,
    setup: Callable[[], Any],
    get_events: Callable[[], Sequence[CalendarEvent]],
    get_uploaded_events: Callable[[Any], Sequence[dict[str, object]]],
    parse_events: Callable[
        [Any, Sequence[CalendarEvent], Sequence[dict[str, object]], bool], None
    ],
    dry_run: bool = False,
) -> None:
    """Run the fetch, read, and synchronization stages in order."""
    # Keep the application flow here so the CLI and tests use the same sequence.
    log.info("LOG START")
    atexit.register(_log_end, log)
    calendar = setup()
    new_events = get_events()
    uploaded_events = get_uploaded_events(calendar)
    parse_events(calendar, new_events, uploaded_events, dry_run)


def _log_end(log: logging.Logger) -> None:
    """Write the end-of-run marker when the process exits."""
    log.info("LOG END\n")


def run_with_error_reporting(
    log: logging.Logger,
    main: Callable[[], None],
    email_errors: Callable[..., object],
    error_email: str,
    error_file: str,
    info_log_file: str,
    script_path: str,
) -> None:
    """Run the application and report failures or reset error history."""
    try:
        main()
    except Exception as err:
        # Report failures through the shared throttled email mechanism.
        log.exception("Run failed")
        email_errors(
            err,
            error_email,
            os.path.abspath(script_path),
            error_file,
            log,
            info_log_file,
        )
    else:
        # A successful run clears any pending error history.
        email_errors(
            None,
            error_email,
            os.path.abspath(script_path),
            error_file,
            log,
            info_log_file,
        )
