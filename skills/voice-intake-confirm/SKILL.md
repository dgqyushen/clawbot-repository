---
name: voice-intake-confirm
description: Handle voice-message workflows where incoming audio must be transcribed, shown back to the user, and only then acted on. Use when working with Telegram or other chat voice notes, local Whisper/faster-whisper transcription, command-by-voice flows, reminders created from speech, or any situation where the recognized text must be visible before execution to prevent mistaken actions.
---

# Voice Intake Confirm

Use this skill when a user sends audio and wants a safe voice-first workflow.

## Core rule

Always show the recognized transcript before taking action from spoken input.

Use this reply pattern whenever practical:

- **识别到：** <transcribed text>
- **执行：** <what will happen next>
- **结果：** <what actually happened>

## Workflow

1. Locate the inbound audio file.
2. Transcribe it with the bundled script or another verified local STT path.
3. Reply with the transcript first so the user can see what was recognized.
4. If the action is low-risk and the intent is clear, continue and report the result in the same reply.
5. If the action is ambiguous or has side effects, ask for confirmation after showing the transcript.

## Risk guidance

Treat these as confirmation-worthy unless the user clearly asked for direct execution:

- reminders / scheduled jobs
- memory writes
- config changes
- command execution
- deletions
- outgoing notifications

For low-risk tasks like summarization, note-taking drafts, or simple Q&A, it is acceptable to show the transcript and continue immediately.

## Local implementation notes

- Prefer local transcription over cloud STT when the local pipeline is available.
- Current local test path uses `scripts/transcribe_telegram_voice.py` in this skill directory.
- Workspace convention: operational helper scripts live in `${OPENCLAW_STATE_DIR:-$HOME/.openclaw}/workspace/scripts/`; if a reusable workflow matures, keep a skill-scoped copy here too.
- Audio/media caches should not accumulate indefinitely; follow the aggressive cleanup policy already maintained via `HEARTBEAT.md`.

## Bundled script

Use `scripts/transcribe_telegram_voice.py` for local testing and deterministic transcription from `.ogg`/Telegram voice files.

Example:

```bash
"${OPENCLAW_STATE_DIR:-$HOME/.openclaw}/venvs/voice-stt/bin/python" \
  "${OPENCLAW_STATE_DIR:-$HOME/.openclaw}/workspace/skills/voice-intake-confirm/scripts/transcribe_telegram_voice.py" \
  /path/to/voice.ogg --model small --device cpu --json
```

If GPU support is later enabled and verified, change `--device` accordingly.
