import arrow
import send_email
import os.path
import post_event as pe

FILE_SEC = 43200
EMAIL_SEC = 86400
EMAIL_FILE = "./email.out"
SEC_PER_DAY = 86400


def main():
        file_tmstmp = 0
        email_tmstmp = 0
        try:
                file_tmstmp = os.path.getmtime(pe.SUCCESS_FILE)
        except Exception as e:
                pe.mlog.info("Could not find success-file. Setting timestamp to zero.")

        try:
                email_tmstmp = os.path.getmtime(EMAIL_FILE)
        except Exception as e:
                pe.mlog.info("Could not find email-file. Setting timestamp to zero.")

        try:
                if ((pe.TODAY.timestamp - file_tmstmp) > FILE_SEC and (pe.TODAY.timestamp - email_tmstmp > EMAIL_SEC)):
                        pe.mlog.info("More than a week since last successfull run. Sending email!")

                        text = """Det er {:.1f} dag(er) siden en vellykket kjøring av Google Calendar-skriptet til skienok.no
                        Sjekk den derre loggen!""".format(((pe.TODAY.timestamp - file_tmstmp) / SEC_PER_DAY))
                        sub = "Hilsen fra Mons"

                        send_email.send_email("landsverk.vegard@gmail.com", "webansvarlig@skienok.no", 
                                "system", "Gmail, privat", sub, text)
                        pe.mlog.info("Marking email sent")
                        with open(EMAIL_FILE, "w") as f:
                                f.write("1")
                else:
                        pe.mlog.info("Last successfull run within chosen timeframe")
        except Exception as e:
                pe.mlog.error(e)

if __name__ == "__main__":
        try:
                pe.mlog.info("CHECK START")
                main()
                pe.mlog.info("CHECK END")
        except Exception as e:
                pe.mlog.error(e)
