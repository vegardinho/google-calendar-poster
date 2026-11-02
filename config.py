import os

import arrow


EMAIL_ERR_FILE = "./email_err.out"
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

CALENDAR_ID = (
    "68ca41b7ea965f90ff1baa2a5999a9d69b279553818c5ba2ef60479b6fe02b11"
    "@group.calendar.google.com"
)
TIMEZONE = "Europe/Oslo"
T_FORMAT = "YYYY-MM-DDTHH:mm:ssZZ"
D_FORMAT = "YYYY-MM-DD"

CRITICAL_LOG_FILE = "logs/critical.log"
ERR_LOG_FILE = "logs/err.log"
INFO_LOG_FILE = "logs/info.log"
DEBUG_LOG_FILE = "logs/all.log"
ERR_EMAIL = "landsverk.vegard@gmail.com"


def env_file_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
