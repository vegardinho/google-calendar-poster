import keyring
import smtplib, ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_email(sender_email, receiver_email, keychain_name, subject, text):
	port = 465  # For SSL
	smtp_server = "smtp.gmail.com"
	password = keyring.get_password(keychain_name, sender_email)
	message = MIMEMultipart("alternative")
	message["Subject"] = subject
	message["From"] = sender_email
	message["To"] = receiver_email

	# Turn these into plain/html MIMEText objects
	plain_text = MIMEText(text, "plain")
	# Add HTML/plain-text parts to MIMEMultipart message
	# The email client will try to render the last part first
	message.attach(plain_text)

	# Create secure connection with server and send email
	context = ssl.create_default_context()
	with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
	    server.login(sender_email, password)
	    server.sendmail(
	        sender_email, receiver_email, message.as_string()
	    )

if __name__ == '__main__':
	text = """Hei,
	Her var det jaggu no tekst, ja"

	Snakkas!"""
	sub = "Hilsen fra Mons"
	send_email("landsverk.vegard@gmail.com", "webansvarlig@skienok.no", "Gmail - epostskript (gcal)", sub, text)

