import os
import smtplib
from email.mime.text import MIMEText

def send_email():
    sender = os.environ["GMAIL_USERNAME"]
    app_pw = os.environ["GMAIL_APP_PASSWORD"]
    to = os.environ.get("TO_EMAIL", sender)

    msg = MIMEText("✅ Your GitHub Action can send email. Next we’ll fetch jobs.")
    msg["Subject"] = "Job Digest Agent — test email"
    msg["From"] = sender
    msg["To"] = to

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(sender, app_pw)
        s.send_message(msg)

if __name__ == "__main__":
    send_email()
