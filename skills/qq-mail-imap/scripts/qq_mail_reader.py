#!/usr/bin/env python3
import argparse
import email
import imaplib
import json
from email.message import Message
from email.header import decode_header
from email.utils import parsedate_to_datetime
from pathlib import Path


def get_openclaw_state_dir() -> Path:
    import os
    return Path(
        os.environ.get('OPENCLAW_STATE_DIR')
        or (Path.home() / '.openclaw')
    ).expanduser()


def load_env(path: str) -> dict:
    data = {}
    for raw in Path(path).read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        data[key.strip()] = value.strip()
    return data


def decode_mime(value: str | None) -> str:
    if not value:
        return ''
    parts = []
    for text, enc in decode_header(value):
        if isinstance(text, bytes):
            parts.append(text.decode(enc or 'utf-8', errors='replace'))
        else:
            parts.append(text)
    return ''.join(parts)


def get_text_from_message(msg: Message) -> str:
    candidates = []
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = (part.get('Content-Disposition') or '').lower()
            if 'attachment' in disposition:
                continue
            if content_type in ('text/plain', 'text/html'):
                payload = part.get_payload(decode=True)
                if payload is None:
                    continue
                charset = part.get_content_charset() or 'utf-8'
                text = payload.decode(charset, errors='replace')
                candidates.append((0 if content_type == 'text/plain' else 1, text))
    else:
        payload = msg.get_payload(decode=True)
        if payload is not None:
            charset = msg.get_content_charset() or 'utf-8'
            candidates.append((0, payload.decode(charset, errors='replace')))
    if not candidates:
        return ''
    candidates.sort(key=lambda x: x[0])
    text = candidates[0][1]
    text = '\n'.join(line.rstrip() for line in text.splitlines())
    return text.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description='Read recent QQ mail via IMAP')
    default_env_file = get_openclaw_state_dir() / 'workspace' / 'config' / 'qq-mail.env'
    parser.add_argument('--env-file', default=str(default_env_file))
    parser.add_argument('--folder', default='INBOX')
    parser.add_argument('--limit', type=int, default=10)
    parser.add_argument('--unseen', action='store_true')
    parser.add_argument('--body-chars', type=int, default=400)
    args = parser.parse_args()

    cfg = load_env(args.env_file)
    host = cfg.get('IMAP_HOST', 'imap.qq.com')
    port = int(cfg.get('IMAP_PORT', '993'))
    user = cfg['IMAP_USER']
    password = cfg['IMAP_PASSWORD']

    client = imaplib.IMAP4_SSL(host, port)
    client.login(user, password)
    client.select(args.folder)
    criterion = '(UNSEEN)' if args.unseen else 'ALL'
    status, data = client.search(None, criterion)
    if status != 'OK':
        raise RuntimeError(f'search failed: {status}')
    ids = [x for x in data[0].split() if x]
    ids = ids[-args.limit:]
    results = []
    for msg_id in reversed(ids):
        status, payload = client.fetch(msg_id, '(RFC822)')
        if status != 'OK' or not payload or not payload[0]:
            continue
        raw = payload[0][1]
        msg = email.message_from_bytes(raw)
        body = get_text_from_message(msg)
        if args.body_chars >= 0:
            body = body[: args.body_chars]
        date_text = msg.get('Date')
        iso_date = None
        try:
            if date_text:
                iso_date = parsedate_to_datetime(date_text).isoformat()
        except Exception:
            iso_date = date_text
        results.append({
            'id': msg_id.decode(),
            'from': decode_mime(msg.get('From')),
            'to': decode_mime(msg.get('To')),
            'subject': decode_mime(msg.get('Subject')),
            'date': iso_date,
            'seen': 'Seen' in str(msg.get('Status', '')),
            'snippet': body,
        })
    client.close()
    client.logout()
    print(json.dumps({'count': len(results), 'messages': results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
