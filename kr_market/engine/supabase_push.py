"""
Supabase 푸시 모듈
=================
각 전략의 latest JSON 파일을 읽어 Supabase 테이블에 upsert 합니다.

테이블 매핑:
  mf_jongga    ← jongga_v2_latest.json
  mf_vcp       ← vcp_signals.json
  mf_flow      ← flow_momentum_latest.json
  mf_narrative ← narrative_momentum_latest.json
  mf_sector    ← sector_rotation_latest.json
  mf_contrarian← contrarian_latest.json

upsert 키:
  mf_jongga    : (stock_code, date)
  나머지        : (ticker, date)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from supabase import create_client, Client

# ── 경로 설정 ──────────────────────────────────────────────────────
_ENGINE_DIR = Path(__file__).resolve().parent
_DATA_DIR   = _ENGINE_DIR.parent / 'data'
_PROJECT_ROOT = _ENGINE_DIR.parent.parent
load_dotenv(_PROJECT_ROOT / '.env')

_SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
_SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')


# ── JSON 파일 → Supabase 행 변환 ───────────────────────────────────

def _rows_jongga(data: dict) -> list[dict]:
    """jongga_v2_latest.json → mf_jongga 행 목록."""
    date_str = data.get('date', '')
    rows = []
    for sig in data.get('signals', []):
        score = sig.get('score', {})
        rows.append({
            'stock_code':    sig.get('stock_code', ''),
            'stock_name':    sig.get('stock_name', ''),
            'market':        sig.get('market', ''),
            'date':          sig.get('signal_date', date_str),
            'grade':         sig.get('grade', ''),
            'score_total':   score.get('total', 0) if isinstance(score, dict) else 0,
            'quality':       sig.get('quality', 0.0),
            'current_price': sig.get('current_price', 0),
            'entry_price':   sig.get('entry_price', 0),
            'stop_price':    sig.get('stop_price', 0),
            'target_price':  sig.get('target_price', 0),
            'r_value':       sig.get('r_value', 0.0),
            'trading_value': sig.get('trading_value', 0),
            'change_pct':    sig.get('change_pct', 0.0),
            'foreign_5d':    sig.get('foreign_5d', 0),
            'inst_5d':       sig.get('inst_5d', 0),
            'themes':        sig.get('themes', []),  # jsonb
        })
    return rows


def _rows_vcp(data: dict) -> list[dict]:
    """vcp_signals.json → mf_vcp 행 목록."""
    date_str = data.get('date', '')
    rows = []
    for sig in data.get('signals', []):
        rows.append({
            'stock_code':  sig.get('code', ''),
            'stock_name':  sig.get('name', ''),
            'market':      sig.get('market', ''),
            'date':        date_str,
            'grade':       sig.get('grade', ''),
            'score':       sig.get('score', 0),
            'c1':          sig.get('c1', 0.0),
            'c2':          sig.get('c2', 0.0),
            'c3':          sig.get('c3', 0.0),
            'r12':         sig.get('r12', 0.0),
            'r23':         sig.get('r23', 0.0),
            'pivot_high':  sig.get('pivot_high', 0.0),
            'foreign_5d':  sig.get('foreign_5d', 0),
            'inst_5d':     sig.get('inst_5d', 0),
        })
    return rows


def _rows_flow(data: dict) -> list[dict]:
    """flow_momentum_latest.json → mf_flow 행 목록."""
    date_str = data.get('date', '')
    rows = []
    for sig in data.get('signals', []):
        rows.append({
            'ticker':           sig.get('ticker', ''),
            'name':             sig.get('name', ''),
            'market':           sig.get('market', ''),
            'date':             sig.get('signal_date', date_str),
            'score':            sig.get('score', 0),
            'flow_score':       sig.get('flow_score', 0),
            'trend_score':      sig.get('trend_score', 0),
            'vol_score':        sig.get('vol_score', 0),
            'foreign_flow':     sig.get('foreign_flow', 0.0),
            'institution_flow': sig.get('institution_flow', 0.0),
            'volume_ratio':     sig.get('volume_ratio', 0.0),
            'signal_strength':  sig.get('signal_strength', ''),
            'price':            sig.get('price', 0.0),
            'change_pct':       sig.get('change_pct', 0.0),
            'ma20':             sig.get('ma20'),
            'ma60':             sig.get('ma60'),
            'trend':            sig.get('trend', ''),
        })
    return rows


def _rows_narrative(data: dict) -> list[dict]:
    """narrative_momentum_latest.json → mf_narrative 행 목록."""
    date_str = data.get('date', '')
    rows = []
    for sig in data.get('signals', []):
        rows.append({
            'ticker':          sig.get('ticker', ''),
            'name':            sig.get('name', ''),
            'market':          sig.get('market', ''),
            'date':            sig.get('signal_date', date_str),
            'score':           sig.get('score', 0),
            'theme':           sig.get('theme', ''),
            'news_sentiment':  sig.get('news_sentiment', 0.0),
            'sns_momentum':    sig.get('sns_momentum', 0),
            'narrative_score': sig.get('narrative_score', 0),
            'news_pts':        sig.get('news_pts', 0),
            'theme_pts':       sig.get('theme_pts', 0),
            'vol_pts':         sig.get('vol_pts', 0),
            'all_themes':      sig.get('all_themes', []),    # jsonb
            'news_reason':     sig.get('news_reason', ''),
            'llm_source':      sig.get('llm_source', ''),
            'price':           sig.get('price', 0.0),
            'change_pct':      sig.get('change_pct', 0.0),
            'theme_peers':     sig.get('theme_peers', 0),   # jsonb
        })
    return rows


def _rows_sector(data: dict) -> list[dict]:
    """sector_rotation_latest.json → mf_sector 행 목록."""
    date_str = data.get('date', '')
    rows = []
    for sig in data.get('signals', []):
        rows.append({
            'ticker':            sig.get('ticker', ''),
            'name':              sig.get('name', ''),
            'market':            sig.get('market', ''),
            'date':              sig.get('signal_date', date_str),
            'score':             sig.get('score', 0),
            'sector':            sig.get('sector', ''),
            'rotation_phase':    sig.get('rotation_phase', ''),
            'relative_strength': sig.get('relative_strength', 0.0),
            'price':             sig.get('price', 0.0),
            'ma20':              sig.get('ma20'),
            'ma60':              sig.get('ma60'),
            'rs_raw':            sig.get('rs_raw', 0.0),
        })
    return rows


def _rows_contrarian(data: dict) -> list[dict]:
    """contrarian_latest.json → mf_contrarian 행 목록."""
    date_str = data.get('date', '')
    rows = []
    for sig in data.get('signals', []):
        rows.append({
            'ticker':               sig.get('ticker', ''),
            'name':                 sig.get('name', ''),
            'market':               sig.get('market', ''),
            'date':                 sig.get('signal_date', date_str),
            'score':                sig.get('score', 0),
            'oversold_score':       sig.get('oversold_score', 0.0),
            'reversal_probability': sig.get('reversal_probability', 0.0),
            'support_level':        sig.get('support_level', 0.0),
            'rsi':                  sig.get('rsi', 0.0),
            'price':                sig.get('price', 0.0),
            'change_pct':           sig.get('change_pct', 0.0),
        })
    return rows


# ── 개별 전략 푸시 ─────────────────────────────────────────────────

# (테이블명, JSON파일명, 행변환함수, upsert 충돌 키)
_STRATEGY_MAP = [
    ('mf_jongga',     'jongga_v2_latest.json',          _rows_jongga,     'stock_code,date'),
    ('mf_vcp',        'vcp_signals.json',                _rows_vcp,        'stock_code,date'),
    ('mf_flow',       'flow_momentum_latest.json',       _rows_flow,       'ticker,date'),
    ('mf_narrative',  'narrative_momentum_latest.json',  _rows_narrative,  'ticker,date'),
    ('mf_sector',     'sector_rotation_latest.json',     _rows_sector,     'ticker,date'),
    ('mf_contrarian', 'contrarian_latest.json',          _rows_contrarian, 'ticker,date'),
]


def _upsert_table(client: Client, table: str, rows: list[dict], on_conflict: str) -> int:
    """
    rows를 테이블에 upsert.
    새로 올리는 건수만큼 기존 테이블에서 가장 오래된 행을 먼저 삭제한다.
    (date ASC → id ASC 기준)
    """
    if not rows:
        return 0

    n = len(rows)

    # 1) 가장 오래된 n개 행의 id 조회
    oldest = (
        client.table(table)
        .select('id')
        .order('date', desc=False)
        .order('id', desc=False)
        .limit(n)
        .execute()
    )
    ids = [r['id'] for r in (oldest.data or [])]

    # 2) 해당 행 삭제
    if ids:
        client.table(table).delete().in_('id', ids).execute()

    # 3) 신규 데이터 upsert
    client.table(table).upsert(rows, on_conflict=on_conflict).execute()
    return n


def push_all(verbose: bool = True) -> dict[str, int]:
    """
    모든 전략의 최신 결과를 Supabase에 upsert.

    Returns:
        {테이블명: upsert된 행 수}
    """
    if not _SUPABASE_URL or not _SUPABASE_KEY:
        raise EnvironmentError('SUPABASE_URL / SUPABASE_KEY 환경변수가 설정되지 않았습니다.')

    client: Client = create_client(_SUPABASE_URL, _SUPABASE_KEY)
    summary: dict[str, int] = {}

    for table, filename, row_builder, on_conflict in _STRATEGY_MAP:
        json_path = _DATA_DIR / filename
        if not json_path.exists():
            if verbose:
                print(f'  [SKIP] {table:<16}  {filename} 파일 없음')
            summary[table] = 0
            continue

        try:
            with open(json_path, encoding='utf-8') as f:
                data = json.load(f)

            rows = row_builder(data)
            count = _upsert_table(client, table, rows, on_conflict)
            summary[table] = count

            if verbose:
                print(f'  [OK]   {table:<16}  -{count}행 삭제 → +{count}행 upsert  ({filename})')

        except Exception as exc:
            print(f'  [ERR]  {table:<16}  {exc}')
            summary[table] = -1

    return summary


def push_one(strategy: str, verbose: bool = True) -> int:
    """단일 전략만 푸시. strategy는 테이블 이름 (예: 'mf_contrarian')."""
    if not _SUPABASE_URL or not _SUPABASE_KEY:
        raise EnvironmentError('SUPABASE_URL / SUPABASE_KEY 환경변수가 설정되지 않았습니다.')

    client: Client = create_client(_SUPABASE_URL, _SUPABASE_KEY)

    for table, filename, row_builder, on_conflict in _STRATEGY_MAP:
        if table != strategy:
            continue

        json_path = _DATA_DIR / filename
        if not json_path.exists():
            print(f'  [SKIP] {filename} 파일 없음')
            return 0

        with open(json_path, encoding='utf-8') as f:
            data = json.load(f)

        rows = row_builder(data)
        count = _upsert_table(client, table, rows, on_conflict)
        if verbose:
            print(f'  [OK]   {table}  {count}행 upsert')
        return count

    raise ValueError(f'알 수 없는 전략: {strategy}')


# ── 독립 실행 ─────────────────────────────────────────────────────

if __name__ == '__main__':
    print('=' * 55)
    print('  Supabase 푸시')
    print('=' * 55)
    result = push_all(verbose=True)
    total = sum(v for v in result.values() if v >= 0)
    errors = sum(1 for v in result.values() if v < 0)
    print(f'\n  합계: {total}행 upsert  오류: {errors}개')
    sys.exit(1 if errors else 0)
