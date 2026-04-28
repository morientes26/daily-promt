#!/usr/bin/env python3
"""
Daily ChatGPT prompt runner.
Reads PROMPT from env, calls OpenAI, sends result via email.
"""

import os
import smtplib
import sys
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from openai import OpenAI

# ── Config from environment variables (GitHub Secrets) ──────────────────────
OPENAI_API_KEY   = os.environ["OPENAI_API_KEY"]
OPENAI_MODEL     = os.getenv("OPENAI_MODEL", "gpt-4o")

EMAIL_SENDER     = os.environ["EMAIL_SENDER"]       # Gmail adresa odosielateľa
EMAIL_PASSWORD   = os.environ["EMAIL_PASSWORD"]     # Gmail App Password (nie bežné heslo)
EMAIL_RECIPIENT  = os.environ["EMAIL_RECIPIENT"]    # kam poslať výsledok

# ── Prompt ───────────────────────────────────────────────────────────────────
# Zmeň SYSTEM_PROMPT a USER_PROMPT podľa potreby,
# alebo ich presuň do GitHub Variables (nie Secrets) ak ich chceš ľahko meniť.

SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", (
    "You are a helpful assistant that provides concise, actionable insights."
))

USER_PROMPT = os.getenv("USER_PROMPT", (
    "Give me one important insight or trend in software engineering "
    "that I should be aware of today. Keep it under 200 words."
))


def call_openai(system: str, user: str) -> str:
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()


def send_email(subject: str, body_text: str, body_html: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = EMAIL_SENDER
    msg["To"]      = EMAIL_RECIPIENT

    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_RECIPIENT, msg.as_string())


def build_html(prompt: str, answer: str, model: str, date: str) -> str:
    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body      {{ font-family: Georgia, serif; max-width: 680px; margin: 40px auto;
                 color: #1a1a1a; background: #fafafa; padding: 20px; }}
    .header   {{ border-bottom: 2px solid #333; padding-bottom: 12px; margin-bottom: 24px; }}
    .label    {{ font-size: 11px; text-transform: uppercase; letter-spacing: 1px;
                 color: #888; margin-bottom: 4px; }}
    .prompt   {{ background: #f0f0f0; border-left: 3px solid #666;
                 padding: 12px 16px; font-style: italic; margin-bottom: 24px; }}
    .answer   {{ line-height: 1.7; font-size: 16px; }}
    .footer   {{ margin-top: 32px; font-size: 12px; color: #aaa; border-top: 1px solid #eee;
                 padding-top: 12px; }}
  </style>
</head>
<body>
  <div class="header">
    <h2 style="margin:0">📬 Daily AI Briefing</h2>
    <div style="color:#888; font-size:13px; margin-top:4px">{date}</div>
  </div>

  <div class="label">Prompt</div>
  <div class="prompt">{prompt}</div>

  <div class="label">Response</div>
  <div class="answer">{answer.replace(chr(10), "<br>")}</div>

  <div class="footer">
    Model: {model} &nbsp;·&nbsp; Sent automatically via GitHub Actions
  </div>
</body>
</html>
"""


def main() -> None:
    date_str = datetime.utcnow().strftime("%A, %d %B %Y")

    print(f"[{date_str}] Calling {OPENAI_MODEL}...")
    answer = call_openai(SYSTEM_PROMPT, USER_PROMPT)
    print(f"Got response ({len(answer)} chars)")

    subject   = f"Daily AI Briefing — {date_str}"
    body_text = f"Prompt:\n{USER_PROMPT}\n\nResponse:\n{answer}"
    body_html = build_html(USER_PROMPT, answer, OPENAI_MODEL, date_str)

    print(f"Sending email to {EMAIL_RECIPIENT}...")
    send_email(subject, body_text, body_html)
    print("Done ✓")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
