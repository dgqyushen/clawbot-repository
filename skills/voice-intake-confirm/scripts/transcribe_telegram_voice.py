#!/root/.openclaw/venvs/voice-stt/bin/python
import argparse
import json
import os
import sys
from faster_whisper import WhisperModel


def main():
    parser = argparse.ArgumentParser(description="Transcribe a Telegram voice file with faster-whisper")
    parser.add_argument("input", help="Path to input audio file (.ogg/.wav/etc.)")
    parser.add_argument("--model", default="small", help="Whisper model size (default: small)")
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"], help="Inference device")
    parser.add_argument("--compute-type", default="auto", help="Compute type for faster-whisper")
    parser.add_argument("--language", default=None, help="Optional language code, e.g. zh or en")
    parser.add_argument("--beam-size", type=int, default=5)
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    device = args.device
    if device == "auto":
        device = "cuda"
        try:
            import ctranslate2  # noqa: F401
        except Exception:
            device = "cpu"

    compute_type = args.compute_type
    if compute_type == "auto":
        compute_type = "float16" if device == "cuda" else "int8"

    model = WhisperModel(args.model, device=device, compute_type=compute_type)
    segments, info = model.transcribe(
        args.input,
        beam_size=args.beam_size,
        language=args.language,
        vad_filter=True,
    )

    parts = []
    items = []
    for seg in segments:
        text = seg.text.strip()
        if text:
            parts.append(text)
        items.append({"start": seg.start, "end": seg.end, "text": seg.text})

    result = {
        "input": args.input,
        "model": args.model,
        "device": device,
        "compute_type": compute_type,
        "language": getattr(info, "language", None),
        "duration": getattr(info, "duration", None),
        "text": " ".join(parts).strip(),
        "segments": items,
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result["text"])


if __name__ == "__main__":
    main()
