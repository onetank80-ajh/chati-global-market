"""Check availability of public captions for one YouTube video. No bypassing access controls."""
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, parse_qs


def video_id(value):
    value = value.strip()
    if re.fullmatch(r'[A-Za-z0-9_-]{11}', value):
        return value
    parsed = urlparse(value)
    if parsed.scheme not in ('http', 'https'):
        raise ValueError('Expected a YouTube video URL or 11-character video ID')
    host = (parsed.hostname or '').lower()
    if host in ('youtube.com', 'www.youtube.com', 'm.youtube.com'):
        if parsed.path == '/watch':
            candidate = parse_qs(parsed.query).get('v', [''])[0]
        elif parsed.path.startswith(('/shorts/', '/live/')):
            candidate = parsed.path.split('/')[2]
        else:
            candidate = ''
    elif host == 'youtu.be':
        candidate = parsed.path.strip('/').split('/')[0]
    else:
        raise ValueError('Unsupported YouTube hostname')
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}', candidate):
        raise ValueError('Invalid video ID')
    return candidate


def probe(url, fetcher=None):
    vid = video_id(url)
    result = {
        'schema_version': 2,
        'checked_at_utc': datetime.now(timezone.utc).isoformat(),
        'video_id': vid,
        'source_url': 'https://www.youtube.com/watch?v=' + vid,
        'status': 'not_checked',
        'transcript_verified': False,
        'language': None,
        'caption_kind': None,
        'caption_characters': 0,
        'error_type': None,
        'error_category': None,
    }
    if fetcher is None:
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
        except ImportError:
            result.update(status='dependency_missing', error_type='ImportError')
            return result
        fetcher = YouTubeTranscriptApi().fetch
    try:
        transcript = fetcher(vid, languages=['ko', 'en'])
        text = ' '.join(str(s.text).strip() for s in transcript if str(s.text).strip())
        if not text:
            result['status'] = 'empty_caption'
            return result
        result.update(status='captions_available', language=getattr(transcript, 'language_code', None),
                      caption_kind='auto_generated' if getattr(transcript, 'is_generated', False) else 'manual_or_unknown',
                      caption_characters=len(text))
        # Keep full transcript private; don't print or commit it.
        result['text'] = text[:250000]
    except Exception as exc:
        name = type(exc).__name__
        categories = {
            'TranscriptsDisabled': 'captions_disabled',
            'NoTranscriptFound': 'language_not_available',
            'VideoUnavailable': 'video_unavailable',
            'RequestBlocked': 'access_blocked',
            'IpBlocked': 'access_blocked',
            'AgeRestricted': 'access_restricted',
            'PoTokenRequired': 'access_restricted',
        }
        result.update(status='caption_fetch_failed', error_type=name,
                      error_category=categories.get(name, 'unknown'))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('youtube_url')
    parser.add_argument('--output', type=Path, default=Path('caption_probe_private.json'))
    args = parser.parse_args()
    result = probe(args.youtube_url)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    # Confirm the output can be parsed; avoid false green workflows.
    json.loads(args.output.read_text(encoding='utf-8'))
    print('status:', result['status'])
    print('video_id:', result['video_id'])
    print('language:', result.get('language'))
    print('caption_characters:', result['caption_characters'])
    print('error_type:', result.get('error_type'))
    print('error_category:', result.get('error_category'))


if __name__ == '__main__':
    main()
