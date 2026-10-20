"""Read publicly available captions only. Returns metadata, never text."""
from urllib.parse import urlparse, parse_qs
import re

def probe(url):
    from youtube_transcript_api import YouTubeTranscriptApi
    p=urlparse(url)
    vid=parse_qs(p.query).get('v',[''])[0]
    if p.hostname not in ('youtube.com','www.youtube.com','m.youtube.com') or not re.fullmatch(r'[A-Za-z0-9_-]{11}',vid):
        return {'status':'invalid_url','error_type':'InvalidVideoUrl'}
    try:
        t=YouTubeTranscriptApi().fetch(vid,languages=['ko','en'])
        count=sum(len(x.text) for x in t)
        return {'status':'captions_available' if count else 'empty_caption','caption_characters':count}
    except Exception as e:
        return {'status':'caption_fetch_failed','error_type':type(e).__name__}
