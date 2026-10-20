"""Probe public YouTube caption availability for a user-provided video.
Does not bypass access restrictions or invent missing transcripts.
Requires: pip install youtube-transcript-api>=1.2,<2
"""
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, parse_qs

def video_id(value):
    value = value.strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", value):
        return value
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Use a YouTube video URL or 11-character video ID")
    host = (parsed.hostname or "").lower()
    if host in ("youtube.com", "www.youtube.com", "m.youtube.com"):
        if parsed.path == "/watch":
            candidate = parse_qs(parsed.query).get("v", [""])[0]
        elif parsed.path.startswith("/shorts/") or parsed.path.startswith("/live/"):
            candidate = parsed.path.split("/")[2]
        else:
            candidate = ""
    elif host == "youtu.be":
        candidate = parsed.path.strip("/").split("/")[0]
    else:
        raise ValueError("Not a supported YouTube URL")
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate):
        raise ValueError("YouTube video ID is missing or invalid")
    return candidate

def probe(url, fetcher=None):
    vid = video_id(url)
    result = {
        "schema_version": 1,
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "video_id": vid,
        "source_url": "https://www.youtube.com/watch?v=" + vid,
        "status": "unavailable",
        "transcript_verified": False,
        "caption_kind": None,
        "language": None,
        "text": None,
        "warnings": ["Public captions may be unavailable for livestreams, restricted videos, or blocked requests."]
    }
    if fetcher is None:
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
        except ImportError:
            result["status"] = "dependency_missing"
            return result
        fetcher = YouTubeTranscriptApi().fetch
    try:
        transcript = fetcher(vid, languages=["ko", "en"])
        snippets = list(transcript)
        text = " ".join(str(s.text).strip() for s in snippets if str(s.text).strip())
        if not text:
            result["status"] = "empty_caption"
            return result
        result.update({
            "status": "captions_available",
            "transcript_verified": False,
            "caption_kind": "auto_generated" if getattr(transcript, "is_generated", None) else "manual_or_unknown",
            "language": getattr(transcript, "language_code", None),
            "text": text[:250000],
            "caption_characters": len(text)
        })
    except Exception as exc:
        # Do not expose exception internals or claim a cause not established.
        result["status"] = "caption_fetch_failed"
        result["error_type"] = type(exc).__name__
    return result

def main():
    p = argparse.ArgumentParser()
    p.add_argument("youtube_url", help="YouTube watch, live, shorts, or youtu.be URL")
    p.add_argument("--output", type=Path, default=Path("data/youtube_caption_probe.json"))
    args = p.parse_args()
    result = probe(args.youtube_url)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\\n", encoding="utf-8")
    print("Caption status:", result["status"])
    print("Result:", args.output)

if __name__ == "__main__":
    main()
