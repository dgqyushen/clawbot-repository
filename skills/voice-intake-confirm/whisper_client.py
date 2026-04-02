"""Whisper HTTP client for Docker containerized transcription service.

This module provides a client for calling a remote Whisper transcription API
running in a Docker container (e.g., faster-whisper-server).
"""

import os
import sys
import json
import requests
from typing import Optional, Dict, Any, List

# Default Whisper service endpoint
# Use host.docker.internal when running inside Docker to reach host
# Or use explicit IP if host.docker.internal doesn't work
DEFAULT_WHISPER_HOST = os.getenv("WHISPER_HOST", "http://host.docker.internal:8000")
DEFAULT_MODEL = os.getenv("WHISPER_MODEL", "small")
DEFAULT_LANGUAGE = os.getenv("WHISPER_LANGUAGE", "zh")
DEFAULT_TIMEOUT = int(os.getenv("WHISPER_TIMEOUT", "60"))


class WhisperClientError(Exception):
    """Base exception for Whisper client errors."""
    pass


class WhisperAPIError(WhisperClientError):
    """Exception for API-level errors (non-2xx responses)."""
    def __init__(self, message: str, status_code: int = None, response_body: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class WhisperClient:
    """Client for Whisper HTTP API running in a Docker container."""
    
    def __init__(
        self,
        host: str = None,
        timeout: int = None,
    ):
        """Initialize the Whisper client.
        
        Args:
            host: Base URL of the Whisper service (e.g., http://localhost:8000)
            timeout: Request timeout in seconds
        """
        self.host = (host or DEFAULT_WHISPER_HOST).rstrip("/")
        self.timeout = timeout or DEFAULT_TIMEOUT
        self.session = requests.Session()
        
    def health_check(self) -> Dict[str, Any]:
        """Check if the Whisper service is healthy.
        
        Returns:
            Health status dict, e.g., {"status": "ok"}
            
        Raises:
            WhisperAPIError: If service is unreachable or unhealthy
        """
        url = f"{self.host}/health"
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError as e:
            raise WhisperAPIError(
                f"Cannot connect to Whisper service at {self.host}. "
                f"Is the Docker container running? ({e})"
            )
        except requests.exceptions.Timeout:
            raise WhisperAPIError(f"Health check timed out after 10s")
        except requests.exceptions.HTTPError as e:
            raise WhisperAPIError(
                f"Health check failed: HTTP {e.response.status_code}",
                status_code=e.response.status_code,
                response_body=e.response.text
            )
    
    def transcribe(
        self,
        audio_path: str,
        model: str = None,
        language: str = None,
        response_format: str = "json",
        temperature: float = 0.0,
        timestamp_granularities: List[str] = None,
    ) -> Dict[str, Any]:
        """Transcribe an audio file using the remote Whisper service.
        
        Args:
            audio_path: Path to the audio file (.ogg, .wav, .mp3, etc.)
            model: Whisper model size (tiny, base, small, medium, large)
                   Default from WHISPER_MODEL env var or "small"
            language: Language code (e.g., "zh", "en", "auto")
                     Default from WHISPER_LANGUAGE env var or "zh"
            response_format: Output format (json, text, srt, verbose_json)
            temperature: Sampling temperature (0.0 for deterministic)
            timestamp_granularities: Granularities for timestamps ["word"] or ["segment"]
            
        Returns:
            Transcription result dict with keys like "text", "segments", etc.
            
        Raises:
            FileNotFoundError: If audio_path doesn't exist
            WhisperAPIError: If transcription fails
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        url = f"{self.host}/v1/audio/transcriptions"
        
        # Prepare form data
        data = {
            "response_format": response_format,
            "temperature": str(temperature),
        }
        
        # Add model and language (use defaults if not specified)
        if model:
            data["model"] = model
        else:
            data["model"] = DEFAULT_MODEL
            
        if language:
            data["language"] = language
        else:
            data["language"] = DEFAULT_LANGUAGE
        
        if timestamp_granularities:
            for i, granularity in enumerate(timestamp_granularities):
                data[f"timestamp_granularities[{i}]"] = granularity
        
        try:
            with open(audio_path, "rb") as audio_file:
                files = {"file": (os.path.basename(audio_path), audio_file)}
                response = self.session.post(
                    url,
                    files=files,
                    data=data,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                
                # Parse response based on format
                if response_format in ("json", "verbose_json"):
                    result = response.json()
                    # Ensure consistent format
                    if isinstance(result, dict):
                        return result
                    elif isinstance(result, str):
                        return {"text": result}
                    else:
                        return {"text": str(result)}
                else:
                    # text, srt formats
                    return {"text": response.text}
                    
        except requests.exceptions.ConnectionError as e:
            raise WhisperAPIError(
                f"Cannot connect to Whisper service at {self.host}. "
                f"Is the Docker container running? ({e})"
            )
        except requests.exceptions.Timeout:
            raise WhisperAPIError(
                f"Transcription timed out after {self.timeout}s. "
                f"Try increasing WHISPER_TIMEOUT or using a smaller model."
            )
        except requests.exceptions.HTTPError as e:
            raise WhisperAPIError(
                f"Transcription failed: HTTP {e.response.status_code}",
                status_code=e.response.status_code,
                response_body=e.response.text
            )
    
    def transcribe_simple(
        self,
        audio_path: str,
        model: str = None,
        language: str = None,
    ) -> str:
        """Simple transcription that returns just the text.
        
        Args:
            audio_path: Path to the audio file
            model: Whisper model size
            language: Language code
            
        Returns:
            Transcribed text as a string
        """
        result = self.transcribe(audio_path, model=model, language=language)
        return result.get("text", "").strip()


# Convenience functions for direct use
def get_client(host: str = None) -> WhisperClient:
    """Get a configured Whisper client."""
    return WhisperClient(host=host)


def transcribe(
    audio_path: str,
    model: str = None,
    language: str = None,
    host: str = None,
) -> Dict[str, Any]:
    """Transcribe audio file using default client configuration.
    
    This is a convenience wrapper for one-off transcriptions.
    """
    client = get_client(host=host)
    return client.transcribe(audio_path, model=model, language=language)


def transcribe_simple(
    audio_path: str,
    model: str = None,
    language: str = None,
    host: str = None,
) -> str:
    """Transcribe audio file and return just the text.
    
    This is the drop-in replacement for the old faster_whisper-based
    transcription function.
    """
    client = get_client(host=host)
    return client.transcribe_simple(audio_path, model=model, language=language)


def check_service(host: str = None) -> bool:
    """Check if the Whisper service is available.
    
    Returns:
        True if service is healthy, False otherwise
    """
    try:
        client = get_client(host=host)
        health = client.health_check()
        return health.get("status") == "ok"
    except WhisperClientError:
        return False


if __name__ == "__main__":
    # CLI interface for testing
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Test Whisper HTTP client"
    )
    parser.add_argument("input", nargs="?", help="Path to input audio file")
    parser.add_argument("--host", default=None, help="Whisper service host")
    parser.add_argument("--model", default=None, help="Model size (tiny/base/small/medium/large)")
    parser.add_argument("--language", default=None, help="Language code (zh/en/etc.)")
    parser.add_argument("--health", action="store_true", help="Check service health only")
    parser.add_argument("--json", action="store_true", help="Output full JSON")
    args = parser.parse_args()
    
    client = get_client(host=args.host)
    
    if args.health:
        try:
            health = client.health_check()
            print(json.dumps(health, ensure_ascii=False, indent=2))
            sys.exit(0)
        except WhisperClientError as e:
            print(f"Health check failed: {e}", file=sys.stderr)
            sys.exit(1)
    
    if not args.input:
        print("Usage: python whisper_client.py <audio_file> [options]", file=sys.stderr)
        print("       python whisper_client.py --health [--host URL]", file=sys.stderr)
        sys.exit(1)
    
    try:
        if args.json:
            result = client.transcribe(
                args.input,
                model=args.model,
                language=args.language,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            text = client.transcribe_simple(
                args.input,
                model=args.model,
                language=args.language,
            )
            print(text)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except WhisperClientError as e:
        print(f"Transcription failed: {e}", file=sys.stderr)
        sys.exit(1)
