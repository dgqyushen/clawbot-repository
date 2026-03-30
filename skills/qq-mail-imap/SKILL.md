---
name: qq-mail-imap
description: Read and summarize QQ Mail over IMAP. Use when the user asks to connect a QQ mailbox, read inbox mail, check unread messages, search recent mail, filter by sender/keyword, or summarize email content from a QQ邮箱 account that already has IMAP enabled and an authorization code available.
---

# QQ Mail IMAP

Use this skill for QQ 邮箱 reading tasks through IMAP.

## Workflow

1. Confirm the mailbox has IMAP enabled and the user has generated an IMAP authorization code.
2. Store credentials in a local env file instead of hardcoding them into scripts or chat replies.
3. Use the bundled script to fetch recent or unread messages.
4. Summarize results for the user instead of dumping raw RFC822 data.
5. If the user exposed an authorization code in chat, recommend rotating it after setup.

## Local credential convention

Prefer a local env file at:

`/root/.openclaw/workspace/config/qq-mail.env`

Expected format:

```env
IMAP_HOST=imap.qq.com
IMAP_PORT=993
IMAP_USER=your_qq@qq.com
IMAP_PASSWORD=your_imap_authorization_code
```

Keep this file out of git.

## Bundled script

Use:

`/root/.openclaw/workspace/skills/qq-mail-imap/scripts/qq_mail_reader.py`

Examples:

```bash
python3 /root/.openclaw/workspace/skills/qq-mail-imap/scripts/qq_mail_reader.py --limit 5
python3 /root/.openclaw/workspace/skills/qq-mail-imap/scripts/qq_mail_reader.py --unseen --limit 10
python3 /root/.openclaw/workspace/skills/qq-mail-imap/scripts/qq_mail_reader.py --limit 20 --body-chars 300
```

For a lightweight “important mail” pass, use the workspace helper:

```bash
python3 /root/.openclaw/workspace/scripts/qq_mail_important.py --unseen --limit 12
```

## Output guidance

Default to a concise mailbox summary:

- sender
- subject
- date
- short snippet
- whether it looks important

Only show more raw content when the user asks.

## Safety notes

- Treat authorization codes as secrets.
- Do not echo credentials back unless the user explicitly asks.
- If a credential was pasted into chat, suggest revoking and regenerating it after successful setup.
- Prefer read-only mailbox workflows unless the user clearly asks for write actions.
