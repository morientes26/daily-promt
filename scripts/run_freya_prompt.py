#!/usr/bin/env python3
"""
Fetch latest posts from a blog URL, pick a theme from prompts.json,
and generate an article using OpenAI in Freya's voice.

Usage: set `OPENAI_API_KEY`, `OPENAI_MODEL`, and optionally `BLOG_URL` env or pass `--blog-url`.
"""

import os
import sys
import json
import argparse
import re
import unicodedata
import requests
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
import random
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from bs4 import BeautifulSoup
from openai import OpenAI


def load_env_file(path: str = ".env") -> None:
    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


load_env_file()
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL")
BLOG_URL = os.environ.get("BLOG_URL") or "https://freyavik.github.io/blog/"

EMAIL_SENDER = os.environ.get("EMAIL_SENDER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")
EMAIL_RECIPIENT = os.environ.get("EMAIL_RECIPIENT")
MAILGUN_API_KEY = os.environ.get("MAILGUN_API_KEY")
MAILGUN_DOMAIN = "epedo.sk"


def fetch_page_text(url: str) -> dict:
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # title heuristics
    title = None
    if soup.find("h1"):
        title = soup.find("h1").get_text(strip=True)
    if not title and soup.title:
        title = soup.title.get_text(strip=True)

    # main content heuristics: <article>, <main>, or fallback to body text
    main = soup.find("article") or soup.find("main")
    if main:
        text = main.get_text(separator="\n", strip=True)
    else:
        body = soup.find("body")
        text = body.get_text(separator="\n", strip=True) if body else soup.get_text(strip=True)

    return {"url": url, "title": title or url, "text": text}


def discover_article_links(home_url: str, max_links: int = 10) -> list:
    resp = requests.get(home_url, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    links = []
    parsed_base = urlparse(home_url)

    # Prefer <article> anchors
    for a in soup.select("article a[href], a[rel=bookmark]"):
        href = a.get("href")
        if not href:
            continue
        full = urljoin(home_url, href)
        if urlparse(full).netloc != parsed_base.netloc:
            continue
        if full not in links:
            links.append(full)
        if len(links) >= max_links:
            return links

    # Fallback: any long anchor text that points to same host
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True)
        if len(text) < 20:
            continue
        full = urljoin(home_url, a["href"])
        if urlparse(full).netloc != parsed_base.netloc:
            continue
        if full not in links:
            links.append(full)
        if len(links) >= max_links:
            break

    return links


def load_prompts(path: str | None = None) -> dict:
    candidates = [path] if path else ["scripts/prompts_freya.json", "scripts/prompts.json"]
    for candidate in candidates:
        if not candidate:
            continue
        if os.path.exists(candidate):
            with open(candidate, "r", encoding="utf-8") as f:
                return json.load(f)

    raise FileNotFoundError("Neither scripts/prompts_freya.json nor scripts/prompts.json exists")


def pick_theme(prompts: dict) -> dict:
    candidates = []
    for value in prompts.values():
        if not isinstance(value, dict):
            continue

        if "theme" in value and "context" in value:
            candidates.append(value)
        elif "user" in value and "system" in value:
            candidates.append(
                {
                    "theme": value.get("user"),
                    "context": value.get("system"),
                }
            )

    if not candidates:
        raise RuntimeError("No usable prompts found; expected 'theme'/'context' or 'user'/'system'")

    return random.choice(candidates)


def call_openai(system: str, user: str) -> str:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set")
    client = OpenAI(api_key=OPENAI_API_KEY)
    model = OPENAI_MODEL or "gpt-4o"
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.7,
        max_tokens=1500,
    )
    return response.choices[0].message.content.strip()


def send_email(subject: str, body_text: str, body_html: str, attachment_path: str | None = None) -> None:
    if not EMAIL_SENDER or not EMAIL_RECIPIENT or not EMAIL_PASSWORD:
        print("Email skipped: missing EMAIL_SENDER/EMAIL_RECIPIENT/EMAIL_PASSWORD", file=sys.stderr)
        return

    message = MIMEMultipart("mixed")
    message["Subject"] = subject
    message["From"] = EMAIL_SENDER
    message["To"] = EMAIL_RECIPIENT

    text_part = MIMEText(body_text, "plain", "utf-8")
    html_part = MIMEText(body_html, "html", "utf-8")
    message.attach(text_part)
    message.attach(html_part)

    if attachment_path and os.path.exists(attachment_path):
        with open(attachment_path, "rb") as fh:
            attachment = MIMEApplication(fh.read(), Name=os.path.basename(attachment_path))
        attachment["Content-Disposition"] = f'attachment; filename="{os.path.basename(attachment_path)}"'
        message.attach(attachment)

    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.starttls()
        smtp.login(EMAIL_SENDER, EMAIL_PASSWORD)
        smtp.send_message(message)


def build_html(title: str, article: str, model: str, date: str) -> str:
    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset=\"utf-8\">
  <style>
    body {{ font-family: Georgia, serif; max-width: 680px; margin: 40px auto; color: #1a1a1a; background: #fafafa; padding: 20px; }}
    .header {{ border-bottom: 2px solid #333; padding-bottom: 12px; margin-bottom: 24px; }}
    .label {{ font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: #888; margin-bottom: 4px; }}
    .answer {{ line-height: 1.7; font-size: 16px; }}
    .footer {{ margin-top: 32px; font-size: 12px; color: #aaa; border-top: 1px solid #eee; padding-top: 12px; }}
  </style>
</head>
<body>
  <div class=\"header\">
    <h2 style=\"margin:0\">Freya Article</h2>
    <div style=\"color:#888; font-size:13px; margin-top:4px\">{date}</div>
  </div>

  <div class=\"label\">Title</div>
  <div class=\"answer\"><strong>{title}</strong></div>

  <div class=\"label\">Article</div>
  <div class=\"answer\">{article.replace(chr(10), '<br>')}</div>

  <div class=\"footer\">
    Model: {model} &nbsp;·&nbsp; Sent automatically via GitHub Actions
  </div>
</body>
</html>
"""


def extract_article_title(article: str, fallback: str | None = None) -> str:
    if not article:
        return fallback or "untitled-article"

    for line in article.splitlines():
        line = line.strip()
        if not line:
            continue

        heading_match = re.match(r"^#{1,6}\s+(.+)$", line)
        if heading_match:
            return heading_match.group(1).strip("# ").strip()

        bold_match = re.match(r"^\*\*(.+)\*\*$", line)
        if bold_match:
            return bold_match.group(1).strip()

        if len(line) <= 120 and not line.startswith(("-", "*", "1.", "2.", "3.")):
            return line

    return fallback or "untitled-article"


def slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    return normalized or "untitled-article"


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--blog-url", dest="blog_url", help="Blog homepage URL to scrape")
    parser.add_argument("--count", dest="count", type=int, default=5, help="Number of latest posts to include")
    parser.add_argument("--save", dest="save", help="Path to save generated article (optional)")
    args = parser.parse_args(argv)

    blog_url = args.blog_url or BLOG_URL
    if not blog_url:
        print("Provide --blog-url or set BLOG_URL environment variable", file=sys.stderr)
        sys.exit(2)

    prompts = load_prompts()
    theme = pick_theme(prompts)

    # theme['theme'] holds the prompt/topic, theme['context'] holds system-style context
    print(f"Using theme: {theme.get('theme')[:80]}...")

    links = discover_article_links(blog_url, max_links=args.count * 2)
    if not links:
        print("No article links discovered on the blog homepage.")
    else:
        print(f"Found {len(links)} candidate links; fetching up to {args.count} posts...")

    posts = []
    for link in links[: args.count]:
        try:
            info = fetch_page_text(link)
            posts.append(info)
        except Exception as exc:
            print(f"Warning: failed to fetch {link}: {exc}")

    # build context from posts
    context_parts = []
    for p in posts:
        snippet = p["text"][:800].strip().replace("\n", " ")
        context_parts.append(f"- {p['title']} ({p['url']}): {snippet}")

    context = "\n".join(context_parts) if context_parts else "(no recent posts found)"

    user_prompt = (
        f"{theme.get('theme')}\n\n" +
        "Context (recent posts from the blog):\n" + context +
        "\n\nWrite a clear, well-structured blog article in Freya's voice (conversational, first person). "
        "Start with a short article title on its own line, then a blank line, then the article body. "
        "Aim for 700-900 words."
    )

    print("Calling OpenAI to generate article...")
    article = call_openai(theme.get("context", ""), user_prompt)

    title = extract_article_title(article, fallback=posts[0]["title"] if posts else None)
    slug = slugify(title)
    now = datetime.utcnow()
    timestamp = now.strftime("%Y%m%dT%H%M%SZ")
    date_str = now.strftime("%Y-%m-%d")
    filename = args.save or f"outputs/{slug}-{timestamp}.md"
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    frontmatter = f"---\ntitle: \"{title}\"\ndate: {date_str}\ndraft: false\n---\n\n"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(frontmatter)
        f.write(article)

    date_str = now.strftime("%A, %d %B %Y")
    subject = f"Freya Article — {title}"
    body_text = f"Title:\n{title}\n\nArticle:\n{article}"
    body_html = build_html(title, article, OPENAI_MODEL or "gpt-4o", date_str)
    send_email(subject, body_text, body_html, attachment_path=filename)

    print(f"Article saved to {filename}")
    print(f"Email sent to {EMAIL_RECIPIENT}")
    print("---\nPreview:\n")
    print(article[:1200])


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
