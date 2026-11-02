# Google Calendar Poster

## Setup

This project uses [uv](https://docs.astral.sh/uv/) for Python and dependency
management. Install Python 3.12, then create the environment and install the
locked dependencies:

```sh
uv sync
```

The shared `python-tools` library is installed as a local path dependency from
the neighboring `../python-tools` repository. It does not need to be
published online.

Provide the required Google API credentials as `credentials.json` in the
project directory. The first run creates `token.pickle` after authorization.
`uv sync` installs the shared `python-tools` modules into this project's
environment before running the application.

## Run

```sh
uv run python main.py
```

To inspect the changes without modifying Google Calendar:

```sh
uv run python main.py --dry-run
```

## Code layout

- `config.py` contains static API, calendar, date-range, and logging settings.
- `models.py` contains typed shapes for Eventor queries and Google Calendar
  event payloads.
- `eventor_client.py` contains Eventor HTTP access, bounded retries, response
  parsing, API-key loading, and optional document retrieval.
- `transformer.py` contains schema-aware Eventor date and field handling,
  calendar payload creation, and duration filtering.
- `calendar_client.py` contains Google Calendar authentication, event listing,
  and event create/update/delete operations.
- `sync.py` contains reconciliation between fetched Eventor events and
  previously uploaded Calendar events.
- `application.py` contains run orchestration and the top-level error/email
  boundary.
- Use `--dry-run` to fetch and compare events while logging intended calendar
  changes without performing them.
- `main.py` is the production application entry point.
- `tests/` contains characterization tests that protect current behavior during
  the restructuring.

## Testing

The project uses `pytest`. Run the complete test suite from the project
directory with:

```sh
uv run pytest -q
```

The `-q` option keeps the output concise. Omit it for more verbose output.

The tests do not contact Eventor or Google Calendar. They use fake HTTP
sessions, Calendar services, loggers, and email handlers so they are safe to
run repeatedly and do not modify real events.

Current coverage is split across:

- `tests/test_eventor_client.py`: Eventor XML/JSON parsing, transient HTTP
  retries, and retry exhaustion.
- `tests/test_calendar_client.py`: Google Calendar pagination and event
  insertion.
- `tests/test_sync.py`: event updates, deletions, uploads, cancelled events,
  and dry-run behavior.
- `tests/test_application.py`: application orchestration and success/failure
  email handling.
- `tests/test_main.py`: schema-aware date parsing, date-only and
  missing-field behavior, calendar payload transformation, duration-limit
  boundaries, query configuration, and compatibility behavior of the main
  entry point.

To run one test file:

```sh
uv run pytest -q tests/test_sync.py
```

To run one named test:

```sh
uv run pytest -q tests/test_sync.py -k dry_run
```
