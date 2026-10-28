"""Fetch recent market headlines from public Google News RSS; headlines are not analysis."""
import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

QUERIES = [
    ('us_market', 'US stock market Federal Reserve Nasdaq S&P 500 when:2d'),
    ('semiconductor', 'Nvidia semiconductor stocks chip market when:2d'),
    ('korea', 'South Korea stock market KOSPI won currency when:2d'),
]

def get_news(group, query):
    params = urllib.parse.urlencode({'q': query, 'hl': 'en-US', 'gl': 'US', 'ceid': 'US:en'})
    req = urllib.request.Request('https://news.google.com/rss/search?' + params,
                                 headers={'User-Agent': 'ChatiMarketBriefing/0.4 (+public RSS)'})
    with urllib.request.urlopen(req, timeout=20) as response:
        xml = response.read(1024 * 1024)
    root = ET.fromstring(xml)
    items = []
    for node in root.findall('./channel/item')[:40]:
        title = (node.findtext('title') or '').strip()
        url = (node.findtext('link') or '').strip()
        published = (node.findtext('pubDate') or '').strip()
        source = node.findtext('source') or ''
        if not title or not url.startswith('https://'):
            continue
        try:
            parsed = parsedate_to_datetime(published)
            if parsed.tzinfo is None:
                continue
            age = (datetime.now(timezone.utc) - parsed).total_seconds() / 3600
            if age < 0 or age > 48:
                continue
            stamp = parsed.astimezone(timezone.utc).isoformat()
        except (TypeError, ValueError):
            continue
        items.append({'category': group, 'title': title[:240], 'url': url,
                      'source': source[:100], 'published_at_utc': stamp})
        if len(items) >= 8:
            break
    return items

def main():
    now = datetime.now(timezone.utc)
    items, errors = [], []
    for group, query in QUERIES:
        try:
            found = get_news(group, query)
            print(group, len(found), 'headlines')
            items.extend(found[:5])
        except Exception as exc:
            errors.append(f'{group}: {type(exc).__name__}: {str(exc)[:100]}')
    if not items:
        raise RuntimeError('No headlines fetched; keep previous news.json. ' + '; '.join(errors))
    data = {'schema_version': 1, 'generated_at_utc': now.isoformat(),
            'generated_at_kst': now.astimezone(ZoneInfo('Asia/Seoul')).isoformat(),
            'source': 'Google News public RSS (headlines/links; not verified article contents)',
            'news_kind': 'headline_links_not_ai_analysis', 'items': items, 'warnings': errors}
    path = Path('data/news.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Saved', path, len(items), 'headlines')

if __name__ == '__main__':
    main()
