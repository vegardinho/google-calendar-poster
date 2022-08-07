import arrow
import send_email
import os.path
import post_event as pe
import traceback
from remove_old_files import remove_old_files

FILE_SEC = 43200
EMAIL_SEC = 86400
EMAIL_FILE = "./email.out"
SEC_PER_DAY = 86400

NOW = pe.TODAY.timestamp
LOGS_EXP_SEC = 2592000


def main():
    check_if_run()
    remove_old_files("./logs/archive/", LOGS_EXP_SEC)


def check_if_run():
    file_tmstmp = 0
    email_tmstmp = 0
    try:
        file_tmstmp = os.path.getmtime(pe.SUCCESS_FILE)
    except Exception as e:
        pe.log.info("Could not find success-file. Setting timestamp to zero.")

    try:
        email_tmstmp = os.path.getmtime(EMAIL_FILE)
    except Exception as e:
        pe.log.info("Could not find email-file. Setting timestamp to zero.")

    try:
        if ((NOW - file_tmstmp) > FILE_SEC and (NOW - email_tmstmp > EMAIL_SEC)):
            pe.log.info("More than a week since last successfull run. Sending email!")

            text = """Det er {:.1f} dag(er) siden en vellykket kjøring av Google
                        Calendar-skriptet til skienok.no. Sjekk den derre loggen!""".format(
                ((NOW - file_tmstmp) / SEC_PER_DAY))
            sub = "Hilsen fra Mons"

            send_email.send_email("landsverk.vegard@gmail.com", "webansvarlig@skienok.no",
                                  "system", "Gmail, privat", sub, text)
            pe.log.info("Marking email sent")
            with open(EMAIL_FILE, "w") as f:
                f.write("1")
        else:
            pe.log.info("Last successfull run within chosen timeframe")
    except Exception as e:
        print(traceback.format_exc())
        pe.log.error(e)


if __name__ == "__main__":
    try:
        pe.log.info("CHECK START")
        main()
        pe.log.info("CHECK END")
    except Exception as e:
        pe.log.error(e)
