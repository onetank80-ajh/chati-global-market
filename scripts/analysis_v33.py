#!/usr/bin/env python3
"""Chati v3.3 experimental explainable analysis (no trades or fabricated transcripts)."""
import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'

def read(name):
    try:
        return json.loads((DATA / name).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}

def signal(item, threshold, invert=False):
    if item.get('status') != 'ok' or not isinstance(item.get('change_percent'), (int, float)):
        return None
    value = float(item['change_percent']) * (-1 if invert else 1)
    return 1 if value > threshold else -1 if value < -threshold else 0

def main():
    now = datetime.now(timezone.utc)
    market, news = read('market.json'), read('news.json')
    now_kst = now.astimezone(ZoneInfo('Asia/Seoul'))
    try:
        snapshot_at = datetime.fromisoformat(market['generated_at_utc'].replace('Z', '+00:00'))
        snapshot_age_hours = (now - snapshot_at).total_seconds() / 3600
    except (KeyError, TypeError, ValueError):
        snapshot_age_hours = None
    is_premarket = now_kst.weekday() < 5 and 7 <= now_kst.hour < 8
    is_fresh = snapshot_age_hours is not None and 0 <= snapshot_age_hours <= 12
    analysis_mode = 'premarket_reference' if is_premarket and is_fresh else 'retrospective_or_unverified'
    m = market.get('markets', {})
    inputs = {
        'sp500': {'weight': 2, 'threshold': .3, 'invert': False, 'label': 'S&P500'},
        'nasdaq': {'weight': 1, 'threshold': .4, 'invert': False, 'label': '나스닥'},
        'sox': {'weight': 2, 'threshold': .5, 'invert': False, 'label': '반도체 SOX'},
        'usdkrw': {'weight': 1, 'threshold': .3, 'invert': True, 'label': '달러/원'},
    }
    factors, available = [], []
    for key, cfg in inputs.items():
        item = m.get(key, {})
        s = signal(item, cfg['threshold'], cfg['invert'])
        factors.append({'key': key, 'name': cfg['label'], 'market_date': item.get('market_date'),
                        'change_percent': item.get('change_percent') if s is not None else None,
                        'signal': s, 'weight': cfg['weight'], 'source': market.get('source', 'unknown')})
        if s is not None:
            available.append((key, s))
    total = sum(f['signal'] * f['weight'] for f in factors if f['signal'] is not None)
    max_total = sum(f['weight'] for f in factors if f['signal'] is not None)
    coverage = len(available) / len(inputs)
    def scenario(index):
        if coverage < .75:
            return {'market': index, 'bias': '판단 보류', 'reason': '필수 지표 수집 부족'}
        # This is an indicative scenario, not a calibrated probability.
        threshold = 3 if index == 'kospi' else 4
        bias = '상승 우세' if total >= threshold else '하락 우세' if total <= -threshold else '중립/혼조'
        return {'market': index, 'bias': bias, 'score': total, 'max_abs_score': max_total,
                'reason': '미국 지수·반도체·환율의 사전 정의된 가중합. 국내 실시간 수급 미포함'}
    source_dates = {f['market_date'] for f in factors if f['signal'] is not None}
    eligible = analysis_mode == 'premarket_reference' and coverage >= .75 and all(
        f['market_date'] and f['market_date'] <= now_kst.date().isoformat()
        for f in factors if f['signal'] is not None)
    if not eligible:
        analysis_mode = 'retrospective_or_unverified'
    warnings = ['규칙 기반 참고 분석이며 학습·검증된 수익 예측 모델이 아닙니다.',
                '한국 지수별 임계값 차이는 실험적 설정이며 백테스트 전에는 성능 우위를 주장할 수 없습니다.',
                '오선 방송의 실제 자막/원문이 제공되지 않아 방송 분석은 수행하지 않았습니다.']
    if len(source_dates) > 1:
        warnings.append('미국 지표별 기준일이 다릅니다. 비교에 주의하세요.')
    if coverage < .75:
        warnings.append('수집 가능한 지표가 75% 미만이라 방향 판단을 보류했습니다.')
    if analysis_mode != 'premarket_reference':
        warnings.append('개장 전 신선한 데이터로 확인되지 않았습니다. 사전 예측이나 적중률 계산에 사용하면 안 됩니다.')
    result = {'schema_version': 1, 'version': '3.3-experimental',
              'generated_at_kst': now.astimezone(ZoneInfo('Asia/Seoul')).isoformat(),
              'analysis_kind': 'explainable_rules_not_ai_not_backtested',
              'analysis_mode': analysis_mode, 'eligible_for_prediction_record': eligible,
              'snapshot_age_hours': round(snapshot_age_hours, 2) if snapshot_age_hours is not None else None,
              'market_snapshot_at': market.get('generated_at_utc'),
              'coverage': round(coverage, 2), 'factors': factors,
              'scenarios': [scenario('kospi'), scenario('kosdaq')],
              'sectors': [{'name': '반도체', 'stocks': ['삼성전자', 'SK하이닉스'],
                           'basis': 'SOX 변동을 참고하며 개별 종목 방향을 확정하지 않음'}],
              'broadcast': {'status': 'not_available', 'transcript_verified': False,
                            'summary': None},
              'news_headline_count': len(news.get('items', [])),
              'risk_checks': ['국내 개장 후 외국인·기관 수급', '국내 거래대금과 시가 갭',
                              '미국 지표 기준일과 휴장 여부', '당일 환율 방향 변화'],
              'warnings': warnings}
    DATA.mkdir(exist_ok=True)
    out = DATA / 'analysis_v33.json'
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Saved', out, 'coverage:', result['coverage'])

if __name__ == '__main__':
    main()
