import os.path
import traceback
from datetime import timedelta

from send_email import send_email
from remove_old_files import remove_old_files

import post_event as pe

FILE_SEC = timedelta(days=.5).total_seconds()
EMAIL_SEC = timedelta(days=1).total_seconds()
EMAIL_FILE = "./email.out"
SEC_PER_DAY = timedelta(days=1).total_seconds()

NOW = pe.TODAY.timestamp()
LOGS_EXP_SEC = timedelta(days=30).total_seconds()


def main():
    check_if_run()
    try:
        remove_old_files("./logs/archive/", LOGS_EXP_SEC)
    except Exception as err:
        pe.log.warning(err)


def check_if_run():
    file_tmstmp = 0
    email_tmstmp = 0
    try:
        file_tmstmp = os.path.getmtime(pe.SUCCESS_FILE)
    except Exception as err:
        pe.log.warning("Could not find success-file. Setting timestamp to zero.")

    try:
        email_tmstmp = os.path.getmtime(EMAIL_FILE)
    except Exception as err:
        pe.log.warning("Could not find email-file. Setting timestamp to zero.")

    try:
        if ((NOW - file_tmstmp) > FILE_SEC and (NOW - email_tmstmp > EMAIL_SEC)):
            pe.log.warning("More than a week since last successfull run. Sending email!")

            text = """Det er {:.1f} dag(er) siden en vellykket kjøring av Google \
                        Calendar-skriptet til skienok.no. Sjekk den derre loggen!""".format(
                ((NOW - file_tmstmp) / SEC_PER_DAY))
            sub = "Hilsen fra Mons"

            send_email("webansvarlig@skienok.no", sub, text)
            pe.log.warning("Marking email as sent")
            with open(EMAIL_FILE, "w") as f:
                f.write("1")
        else:
            pe.log.info("Last successfully run within chosen timeframe")
    except Exception as err:
        print(traceback.format_exc())
        pe.log.error(err)


if __name__ == "__main__":
    try:
        pe.log.info("CHECK START")
        main()
        pe.log.info("CHECK END")
    except Exception as e:
        pe.log.error(e)

# TODO: kombiner med email_errors i python-tools
