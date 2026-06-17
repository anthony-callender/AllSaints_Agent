from __future__ import annotations

import argparse
import email
import imaplib
import json
import os
from email.message import Message
from pathlib import Path

from form_to_packet import parse_form
from local_env import ROOT, load_local_env
from weekly_packet import packet_text, slugify


WORK = ROOT / "work"


def message_text(message: Message) -> str:
    if message.is_multipart():
        parts = []
        for part in message.walk():
            if part.get_content_maintype() == "multipart":
                continue
            if part.get_content_type() != "text/plain":
                continue
            payload = part.get_payload(decode=True)
            if payload:
                parts.append(payload.decode(part.get_content_charset() or "utf-8", errors="replace"))
        return "\n".join(parts).strip()

    payload = message.get_payload(decode=True)
    if payload:
        return payload.decode(message.get_content_charset() or "utf-8", errors="replace").strip()
    return str(message.get_payload()).strip()


def write_packet(text: str, output_dir: Path) -> tuple[Path, Path, Path]:
    data = parse_form(text)
    output_dir.mkdir(parents=True, exist_ok=True)
    service_date = data.get("service_date") or "undated"
    title = data.get("sermon_title") or data.get("service_title") or "sermon"
    stem = f"{service_date}-{slugify(title)}"

    raw_path = output_dir / f"{stem}-form.txt"
    json_path = output_dir / f"{stem}.json"
    packet_path = output_dir / f"{stem}.md"
    raw_path.write_text(text, encoding="utf-8")
    json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    packet_path.write_text(packet_text(data), encoding="utf-8")
    return raw_path, json_path, packet_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch the latest sermon form email and generate a packet.")
    parser.add_argument("--mailbox", default="INBOX", help="IMAP mailbox to search.")
    parser.add_argument("--max", type=int, default=25, help="Maximum latest messages to inspect.")
    parser.add_argument("--output-dir", type=Path, default=WORK, help="Output directory.")
    args = parser.parse_args()

    load_local_env()
    username = os.environ.get("SERMON_FORMS_EMAIL")
    password = os.environ.get("SERMON_FORMS_APP_PASSWORD")
    if not username or not password:
        raise SystemExit("Set SERMON_FORMS_EMAIL and SERMON_FORMS_APP_PASSWORD in .env.")

    with imaplib.IMAP4_SSL("imap.gmail.com") as imap:
        imap.login(username, password)
        imap.select(args.mailbox)
        status, data = imap.search(None, "ALL")
        if status != "OK" or not data or not data[0]:
            raise SystemExit("No messages found.")

        ids = data[0].split()
        for message_id in reversed(ids[-args.max :]):
            status, fetched = imap.fetch(message_id, "(RFC822)")
            if status != "OK" or not fetched:
                continue
            raw = fetched[0][1]
            message = email.message_from_bytes(raw)
            subject = str(message.get("subject", ""))
            text = message_text(message)
            if "sermon" not in f"{subject}\n{text}".lower():
                continue
            raw_path, json_path, packet_path = write_packet(text, args.output_dir)
            print(raw_path)
            print(json_path)
            print(packet_path)
            return 0

    raise SystemExit(f"No sermon form email found in the latest {args.max} messages.")


if __name__ == "__main__":
    raise SystemExit(main())

