import os
import smtplib
from email.message import EmailMessage
from datetime import datetime
from zoneinfo import ZoneInfo


required = [
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
    "EMAIL_FROM",
    "EMAIL_TO",
    "NEWSLETTER_URL",
]

missing = [key for key in required if not os.getenv(key)]
if missing:
    print(f"Missing required environment variables: {', '.join(missing)}")
    raise SystemExit(1)

smtp_host = os.environ["SMTP_HOST"]
smtp_port = int(os.environ["SMTP_PORT"])
smtp_username = os.environ["SMTP_USERNAME"]
smtp_password = os.environ["SMTP_PASSWORD"]
email_from = os.environ["EMAIL_FROM"]
email_to = [addr.strip() for addr in os.environ["EMAIL_TO"].split(",") if addr.strip()]
newsletter_url = os.environ["NEWSLETTER_URL"]

today = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y년 %-m월 %-d일")

subject = f"[HR 주간 뉴스레터] {today} 발행"
body = (
    f"이번 주 HR 뉴스레터가 발행되었습니다.\n\n"
    f"열람 링크: {newsletter_url}\n\n"
    f"이 메일은 GitHub Actions에서 자동 발송되었습니다."
)

message = EmailMessage()
message["Subject"] = subject
message["From"] = email_from
message["To"] = ", ".join(email_to)
message.set_content(body)

with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
    server.login(smtp_username, smtp_password)
    server.send_message(message)

print("Email sent successfully.")
