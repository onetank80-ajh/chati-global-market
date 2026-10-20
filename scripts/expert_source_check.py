"""v3.5: discover two public market video sources and test captions.

Only writes metadata; no transcript content is saved. Discovery failure is not
proof that a channel has no videos. No claims about expert opinions are made.
"""
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

SOURCES = (
    {'key': 'hankyung', 'name': '한경 글로벌마켓', 'search': '김현석 월스트리트나우 한경 글로벌마켓 최근 미국 증시'},
    {'key': 'bloomberg', 'name': 'Bloomberg Television', 'search': 'Bloomberg Television markets latest'},
)


def check_source(source, discover, probe):
    result = {'source': source['key'], 'name': source['name'],
              'discovery': 'unavailable', 'caption_status': 'not_tested',
              'video_id': None, 'video_url': None, 'caption_characters': 0,
              'error_type': None, 'notes': []}
    try:
        entry = discover(source['search'])
        if not entry:
            result['notes'].append('No video found by this discovery method; not evidence of no videos.')
            return result
        vid = entry.get('id')
        if not isinstance(vid, str) or not re.fullmatch(r'[A-Za-z0-9_-]{11}', vid):
            result['notes'].append('Discovery returned no valid YouTube video ID.')
            return result
        result.update(discovery='found', video_id=vid, video_url='https://www.youtube.com/watch?v='+vid)
    except Exception as exc:
        result['error_type'] = type(exc).__name__
        result['notes'].append('Discovery failed; check network/service restrictions.')
        return result
    try:
        info = probe(result['video_url'])
        result['caption_status'] = info.get('status', 'unknown')
        result['caption_characters'] = info.get('caption_characters', 0)
        result['error_type'] = info.get('error_type')
        if result['caption_status'] != 'captions_available':
            result['notes'].append('Caption access failed or unavailable; cannot infer absence of subtitles.')
    except Exception as exc:
        result['caption_status'] = 'probe_error'
        result['error_type'] = type(exc).__name__
    return result


def discover_video(query):
    from yt_dlp import YoutubeDL
    opts = {'quiet': True, 'no_warnings': True, 'skip_download': True,
            'extract_flat': True, 'socket_timeout': 15, 'retries': 1,
            'extractor_retries': 1, 'ignoreerrors': True}
    with YoutubeDL(opts) as ydl:
        data = ydl.extract_info('ytsearch1:'+query, download=False)
    return next((v for v in (data or {}).get('entries', []) if v), None)


def caption_probe(url):
    from v35_youtube_caption_probe import probe
    return probe(url)


def run(discover=discover_video, probe=caption_probe):
    return {'schema_version': 1, 'generated_at_utc': datetime.now(timezone.utc).isoformat(),
            'method': 'youtube_search_and_public_caption_probe',
            'disclaimer': 'No expert statements verified. Search results may not be latest or official channel.',
            'sources': [check_source(s, discover, probe) for s in SOURCES]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='v35_expert_source_status.json')
    args = parser.parse_args()
    result = run()
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    for item in result['sources']:
        print(item['name'], '| discovery:', item['discovery'], '| caption:', item['caption_status'], '| error:', item['error_type'])
    print('No transcripts are printed or saved.')

if __name__ == '__main__':
    main()
