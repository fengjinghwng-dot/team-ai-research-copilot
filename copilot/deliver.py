"""Persist-first delivery: ambiguous results are not automatically retried (avoid spam)."""
import html
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from urllib.parse import urlparse

import httpx
from sqlalchemy.dialects.postgresql import insert

from .config import settings
from .db import session
from .models import Delivery


def paper_link(team_id, paper_id):
    return f"{settings().workspace_url.rstrip('/')}/teams/{team_id}/papers/{paper_id}"


def send_once(key: str, url: str, payload: dict, headers: dict | None = None):
    with session() as db:
        claimed = db.scalar(insert(Delivery).values(key=key, state="sending")
                            .on_conflict_do_nothing().returning(Delivery.key))
        if not claimed:
            return
    try:
        response = httpx.post(url, json=payload, headers=headers or {}, timeout=30)
        response.raise_for_status()
        if "slack.com" in url:
            if response.text.strip() != "ok":
                raise ValueError("Slack did not acknowledge delivery")
        elif "resend.com" not in url:
            data = response.json()
            if data.get("code", data.get("errcode", 0)) != 0:
                raise ValueError("IM provider rejected delivery")
        state, error = "sent", None
    except Exception as exc:
        state, error = "uncertain", type(exc).__name__
    with session() as db:
        record = db.get(Delivery, key)
        record.state, record.error = state, error


def push_group(team_id, day, items: list[dict]):
    cfg = settings()
    if not cfg.im_provider or not cfg.im_webhook_url or cfg.im_team_id != str(team_id) or not items:
        return
    hosts = {"feishu": {"open.feishu.cn", "open.larksuite.com"},
             "wecom": {"qyapi.weixin.qq.com"}, "slack": {"hooks.slack.com"}}
    parsed = urlparse(cfg.im_webhook_url)
    if parsed.scheme != "https" or parsed.hostname not in hosts[cfg.im_provider]:
        raise ValueError("IM webhook host does not match provider")
    if cfg.im_provider == "slack":
        blocks = [{"type": "header", "text": {"type": "plain_text", "text": f"研究日报 · {day}"}}]
        for item in items[:5]:
            blocks.extend([
                {"type": "section", "text": {"type": "plain_text", "text": (
                    item["title"] + "\n" + item.get("innovation", item["reason"]))[:2000]}},
                {"type": "actions", "elements": [{"type": "button", "text": {
                    "type": "plain_text", "text": "查看解读 / 认领"},
                    "url": paper_link(team_id, item["paper_id"])}]},
            ])
        payload = {"text": f"研究日报 {day}", "blocks": blocks}
    elif cfg.im_provider == "feishu":
        elements = []
        for item in items[:5]:
            elements.extend([
                {"tag": "div", "text": {"tag": "plain_text", "content":
                    item["title"] + "\n" + item.get("innovation", item["reason"])}},
                {"tag": "action", "actions": [{"tag": "button", "text": {
                    "tag": "plain_text", "content": "查看解读 / 认领"},
                    "url": paper_link(team_id, item["paper_id"])}]},
            ])
        payload = {"msg_type": "interactive", "card": {"header": {"title": {
            "tag": "plain_text", "content": f"研究日报 · {day}"}}, "elements": elements}}
    else:
        lines = [f"研究日报 · {day}"]
        for item in items[:5]:
            safe_title = item["title"].replace("[", "(").replace("]", ")")
            lines.append(f"[{safe_title}]({paper_link(team_id, item['paper_id'])})")
            lines.append(item.get("innovation", item["reason"])[:150])
        # WeCom's markdown payload is limited in bytes.
        content = "\n\n".join(lines)
        while len(content.encode()) > 3900:
            content = content[:-50]
        payload = {"msgtype": "markdown", "markdown": {"content": content}}
    send_once(f"group:{team_id}:{day}", cfg.im_webhook_url, payload)


def push_email(user, team_id, day, personal: dict):
    cfg = settings()
    smtp_ready = bool(cfg.smtp_host and cfg.smtp_username and cfg.smtp_password)
    if not (cfg.resend_api_key or smtp_ready) or not cfg.email_from or not user.email_opt_in:
        return
    lines = [f"{day} 个人研究日报\n"]
    for item in personal["items"]:
        lines.extend([item["title"], item.get("summary", item["reason"]), paper_link(team_id, item["paper_id"]), ""])
    text = "\n".join(lines)
    key = f"email:{team_id}:{user.id}:{day}"
    if cfg.resend_api_key:
        send_once(key, "https://api.resend.com/emails", {
            "from": cfg.email_from, "to": [user.email], "subject": f"研究日报 · {day}",
            "text": text}, headers={"Authorization": f"Bearer {cfg.resend_api_key}",
            "Idempotency-Key": f"digest-{team_id}-{user.id}-{day}"})
        return
    with session() as db:
        claimed = db.scalar(insert(Delivery).values(key=key, state="sending")
                            .on_conflict_do_nothing().returning(Delivery.key))
        if not claimed:
            return
    try:
        message = EmailMessage()
        message['From'], message['To'] = cfg.email_from, user.email
        message['Subject'] = f"研究日报 · {day}"
        message['Date'], message['Message-ID'] = formatdate(), make_msgid()
        message.set_content(text)
        message.add_alternative('<html><body><pre style="white-space:pre-wrap">' +
                                html.escape(text) + '</pre></body></html>', subtype='html')
        context = ssl.create_default_context()
        if cfg.smtp_port == 465:
            connection = smtplib.SMTP_SSL(cfg.smtp_host, 465, timeout=30, context=context)
        else:
            connection = smtplib.SMTP(cfg.smtp_host, 587, timeout=30)
            connection.starttls(context=context)
        with connection:
            connection.login(cfg.smtp_username, cfg.smtp_password)
            connection.send_message(message)
        state, error = 'sent', None
    except Exception as exc:
        state, error = 'uncertain', type(exc).__name__
    with session() as db:
        record = db.get(Delivery, key)
        record.state, record.error = state, error
