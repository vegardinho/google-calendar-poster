import os

import arrow


PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(PROJECT_DIR, "config")
LOG_DIR = os.path.join(PROJECT_DIR, "logs")
STATE_DIR = os.path.join(PROJECT_DIR, "state")


def env_file_path() -> str:
    """Return the path to this application's local configuration file."""
    return os.path.join(CONFIG_DIR, ".env")


def _env_value(name: str, default: str) -> str:
    """Read a named value from `.env`, returning `default` when absent."""
    # Keep configuration file loading local to this project and avoid requiring
    # a dotenv dependency for one simple setting.
    try:
        with open(env_file_path(), encoding="utf-8") as env_file:
            for line in env_file:
                variable, separator, configured_value = line.partition("=")
                if separator and variable.strip() == name:
                    configured_value = configured_value.strip().strip("\"'")
                    if configured_value:
                        return configured_value
    except FileNotFoundError:
        pass

    return default


EMAIL_ERR_FILE = os.path.join(STATE_DIR, "email_err.out")
GOOGLE_CREDENTIALS_FILE = os.path.join(CONFIG_DIR, "credentials.json")
EMAIL_PASSWORD_FILE = os.path.join(CONFIG_DIR, ".email_pwd")
GOOGLE_TOKEN_FILE = os.path.join(STATE_DIR, "token.pickle")
SUCCESS_FILE = os.path.join(STATE_DIR, "success.out")
EVENTOR_API_URL = "https://eventor.orientering.no/api"
EVENTOR_EVENT_URL = "https://eventor.orientering.no/Events/Show/{}"
EVENTOR_API_KEY_VARIABLE = "EVENTOR_API_KEY"

EVENTOR_EVENT_QUERIES = (
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

MONTHS_FWD = 12
MONTHS_BACK = 2
MAX_EVENT_DURATION_DAYS = 7
TODAY = arrow.now()
START_DATE = TODAY.shift(months=-MONTHS_BACK)
END_DATE = TODAY.shift(months=+MONTHS_FWD)

# The .env value is useful for a shared calendar; "primary" keeps local setup
# working when no project-specific calendar has been configured.
CALENDAR_ID = _env_value("CALENDAR_ID", "primary")

TIMEZONE = "Europe/Oslo"
T_FORMAT = "YYYY-MM-DDTHH:mm:ssZZ"
D_FORMAT = "YYYY-MM-DD"

CRITICAL_LOG_FILE = os.path.join(LOG_DIR, "critical.log")
ERR_LOG_FILE = os.path.join(LOG_DIR, "err.log")
INFO_LOG_FILE = os.path.join(LOG_DIR, "info.log")
DEBUG_LOG_FILE = os.path.join(LOG_DIR, "all.log")
ERR_EMAIL = "landsverk.vegard@gmail.com"
