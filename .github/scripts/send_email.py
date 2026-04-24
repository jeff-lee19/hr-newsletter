import os
import smtplib
from email.message import EmailMessage
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import re


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
newsletter_html = Path("hr_monday_newsletter.html").read_text(encoding="utf-8")

today = datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y년 %-m월 %-d일")


def extract_preview(html):
    match = re.search(r"<h2[^>]*>이번 주 핵심 브리핑</h2>\s*<div[^>]*>(.*?)</div>", html, re.DOTALL)
    if not match:
        return "이번 주 핵심: AI 채용, 노무 리스크, 국내 인사 변화"
    text = re.sub(r"<[^>]+>", " ", match.group(1))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:90]

preview_text = extract_preview(newsletter_html)
subject = f"[HR 주간 뉴스레터] {today} 발행 | {preview_text[:24]}"
body = (
    f"이번 주 HR 뉴스레터가 발행되었습니다.\n\n"
    f"웹에서 보기: {newsletter_url}\n\n"
    f"이 메일은 GitHub Actions에서 자동 발송되었습니다."
)

banner = (
    '<div style="display:none;max-height:0;overflow:hidden;opacity:0;">'
    f"{preview_text}"
    "</div>"
    '<div style="max-width: 600px; margin: 0 auto 16px auto; font-family: Arial, sans-serif;">'
    f'<p style="margin: 0 0 12px 0; color: #475569; font-size: 13px; text-align: center;">'
    f'메일이 잘리거나 브라우저에서 보려면 <a href="{newsletter_url}" style="color: #1d4ed8; font-weight: bold; text-decoration: none;">웹에서 보기</a>'
    f"</p></div>"
)

body_tag_start = newsletter_html.find("<body")
if body_tag_start == -1:
    html_body = banner + newsletter_html
else:
    body_tag_end = newsletter_html.find(">", body_tag_start)
    if body_tag_end == -1:
        html_body = banner + newsletter_html
    else:
        html_body = (
            newsletter_html[: body_tag_end + 1]
            + banner
            + newsletter_html[body_tag_end + 1 :]
        )

message = EmailMessage()
message["Subject"] = subject
message["From"] = email_from
message["To"] = ", ".join(email_to)
message.set_content(body)
message.add_alternative(html_body, subtype="html")

with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
    server.login(smtp_username, smtp_password)
    server.send_message(message)

print("Email sent successfully.")
