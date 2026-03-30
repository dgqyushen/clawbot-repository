#!/bin/bash
# Video Summarize Script - Download YouTube audio and transcribe with local Whisper
# Uses isolated venv: /root/.openclaw/venvs/video-summarize

set -e

VIDEO_URL="$1"
if [ -z "$VIDEO_URL" ]; then
    echo "Usage: $0 <youtube-url>"
    exit 1
fi

VENV_PATH="/root/.openclaw/venvs/video-summarize"

echo "=== Video Summarize Pipeline ==="
echo "URL: $VIDEO_URL"
echo "Venv: $VENV_PATH"
echo ""

# Setup paths
WORK_DIR="/tmp/video-summarize-$$"
mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

# Check dependencies
echo "[1/5] Checking dependencies..."

# Check ffmpeg (system package)
if ! command -v ffmpeg &> /dev/null; then
    echo "Installing ffmpeg..."
    apt-get update -qq && apt-get install -y -qq ffmpeg
fi

# Setup venv if not exists
if [ ! -d "$VENV_PATH" ]; then
    echo "Creating video-summarize venv..."
    python3 -m venv "$VENV_PATH"
    
    # Download yt-dlp binary directly (avoid pip timeout)
    echo "Downloading yt-dlp binary..."
    wget -q -O "$VENV_PATH/bin/yt-dlp" https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_linux
    chmod +x "$VENV_PATH/bin/yt-dlp"
    
    # Install faster-whisper in venv
    echo "Installing faster-whisper..."
    "$VENV_PATH/bin/python" -m pip install -q faster-whisper
    
    echo "✓ venv created and packages installed"
else
    echo "✓ venv exists"
fi

# Use venv binaries directly
YTDLP="$VENV_PATH/bin/yt-dlp"
PYTHON="$VENV_PATH/bin/python"

echo "✓ Dependencies ready"

# Download audio
echo ""
echo "[2/5] Downloading audio..."
"$YTDLP" -f 'bestaudio[ext=m4a]/bestaudio' \
    --extract-audio \
    --audio-format wav \
    --audio-quality 0 \
    -o "audio.%(ext)s" \
    "$VIDEO_URL"

AUDIO_FILE=$(ls audio.* 2>/dev/null | head -1)
if [ -z "$AUDIO_FILE" ]; then
    echo "✗ Download failed"
    exit 1
fi

echo "✓ Downloaded: $AUDIO_FILE"

# Transcribe with faster-whisper
echo ""
echo "[3/5] Transcribing audio with faster-whisper..."
echo "(Using medium model for speed/quality balance)"

# Run transcription using venv Python
"$PYTHON" - "$AUDIO_FILE" "$WORK_DIR/transcript.txt" << 'PYEOF'
from faster_whisper import WhisperModel
import sys

audio_file = sys.argv[1]
output_file = sys.argv[2]

model = WhisperModel("medium", device="cpu", compute_type="int8")
segments, info = model.transcribe(audio_file, beam_size=5)

with open(output_file, "w", encoding="utf-8") as f:
    f.write(f"Detected language: {info.language}\n")
    f.write(f"Probability: {info.language_probability:.2f}\n\n")
    for segment in segments:
        f.write(f"[{segment.start:.2f}s -> {segment.end:.2f}s] {segment.text}\n")

print("Transcription complete")
PYEOF

TRANSCRIPT="$WORK_DIR/transcript.txt"
if [ ! -f "$TRANSCRIPT" ]; then
    echo "✗ Transcription failed"
    exit 1
fi

echo "✓ Transcribed to: $TRANSCRIPT"

# Move result to workspace
RESULT_PATH="/tmp/transcript_$(date +%s).txt"
cp "$TRANSCRIPT" "$RESULT_PATH"

echo ""
echo "[4/5] Transcript saved: $RESULT_PATH"
echo ""
echo "[5/5] Done! Transcript preview:"
head -100 "$RESULT_PATH"
echo ""
echo "=== Full path: $RESULT_PATH ==="