---
name: video-summarize
description: Download, transcribe, and summarize YouTube videos using local Whisper model. Use when the user wants to summarize a YouTube video, extract key points from video content, or get transcripts from online videos.
---

# Video Summarize Skill

Download, transcribe, and summarize YouTube videos using local Whisper model.

## Prerequisites

- `ffmpeg` - Audio/video processing (system package)
- `video-summarize` venv with:
  - `yt-dlp` - YouTube video downloader
  - `faster-whisper` - Local transcription

## Environment Setup

```bash
# Create isolated venv
python3 -m venv /root/.openclaw/venvs/video-summarize
source /root/.openclaw/venvs/video-summarize/bin/activate
pip install yt-dlp faster-whisper
```

## Workflow

1. **Download audio** from YouTube URL using `yt-dlp`
2. **Transcribe** using `faster-whisper` (local, no API cost)
3. **Summarize** the transcript using LLM

## Usage

```bash
# Quick summarize
openclaw skill video-summarize --url "https://youtube.com/watch?v=..."

# Or direct script
bash skills/video-summarize/scripts/summarize.sh "YOUTUBE_URL"
```

## Implementation

- Isolated virtual environment for all Python dependencies
- Downloads best audio format (m4a/webm)
- Converts to WAV for Whisper compatibility
- Uses faster-whisper `medium` model
- Returns full transcript + structured summary
