"""관측자료 정규화와 내보내기 경계. UI 없이 검증할 수 있도록 분리한다."""
import io
import csv
from datetime import timedelta

import numpy as np
import pandas as pd

MS_TO_KT = 1.94384
MAX_FILES = 20
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024
MAX_ROWS = 300_000


def prepare_observations(frame, start_date=None, end_date=None):
    """단일 지점·정시 자료를 정규화하고 제외 사유를 보존한다.

    동일 시각·동일 측정은 한 번만 사용하고, 충돌한 측정은 모두 제외한다.
    날짜 필터 밖 자료는 분석대상 자체가 아니므로 품질 분모에서도 제외한다.
    """
    required = {'tm', 'wd', 'ws'}
    if not frame.columns.is_unique or not required.issubset(frame.columns):
        raise ValueError("일시·풍향·풍속 열이 필요합니다.")
    df = frame.copy()
    df['원본_일시'] = df['tm']
    df['원본_풍향'] = df['wd']
    df['원본_풍속'] = df['ws']
    df['tm'] = pd.to_datetime(df['tm'], errors='coerce', format='mixed')
    if isinstance(df['tm'].dtype, pd.DatetimeTZDtype) or not pd.api.types.is_datetime64_any_dtype(df['tm']):
        raise ValueError("관측시각은 시간대 표기 없는 한국 표준시여야 합니다.")
    if start_date is not None:
        df = df[df['tm'].isna() | (df['tm'] >= pd.Timestamp(start_date))]
    if end_date is not None:
        df = df[df['tm'].isna() | (df['tm'] < pd.Timestamp(end_date + timedelta(days=1)))]
    if 'stnId' in df:
        station = df['stnId'].astype('string').str.strip().str.replace(r'\.0$', '', regex=True).str.lstrip('0')
        if station.isna().any() or not station.str.fullmatch(r'\d+').all() or station.nunique() > 1:
            raise ValueError("자료에는 하나의 지점번호만 있어야 합니다.")
        df['stnId'] = station
    for col in ('wd', 'ws'):
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df['ws_kt'] = df['ws'] * MS_TO_KT
    reason = pd.Series('', index=df.index, dtype='string')
    invalid_wind = (~np.isfinite(df['wd']) | ~df['wd'].between(0, 360)
                    | ~np.isfinite(df['ws_kt']) | (df['ws'] < 0))
    reason.loc[invalid_wind] = '풍향·풍속 결측 또는 범위 오류'
    for flag in ('wdQcflg', 'wsQcflg'):
        if flag in df:
            text = df[flag].astype('string').str.strip()
            flag_value = pd.to_numeric(text, errors='coerce')
            # 공란은 미제공, 0은 정상. 나머지 명시적 플래그는 보수적으로 제외한다.
            bad_flag = text.notna() & text.ne('') & (flag_value.isna() | flag_value.ne(0))
            reason.loc[bad_flag] = '풍향·풍속 품질검사 플래그 오류'
    non_hour = df['tm'].notna() & df['tm'].ne(df['tm'].dt.floor('h'))
    reason.loc[df['tm'].isna() | non_hour] = '일시 결측 또는 정시 자료 아님'
    # 품질 플래그가 다르면 정상값 우선 추정 없이 중복 충돌로 취급한다.
    signature = ['tm', 'wd', 'ws'] + [c for c in ('wdQcflg', 'wsQcflg') if c in df]
    exact_dup = df['tm'].notna() & df.duplicated(subset=signature, keep='first')
    reason.loc[exact_dup] = '동일 관측 중복'
    unique = df[~exact_dup & df['tm'].notna()]
    conflicting_times = unique.loc[unique.duplicated('tm', keep=False), 'tm']
    reason.loc[df['tm'].isin(conflicting_times)] = '동일 시각 관측값 충돌'
    df['제외사유'] = reason
    valid = df.loc[reason.eq('')].drop(columns=['제외사유', '원본_일시', '원본_풍향', '원본_풍속']).sort_values('tm').reset_index(drop=True)
    invalid = df.loc[reason.ne('')].reset_index(drop=True)
    return valid, invalid


def parse_aws_csv(uploaded_files, start_date=None, end_date=None):
    error = lambda message: (None, None, message, (None, None))
    if not uploaded_files:
        return error("업로드된 파일이 없습니다.")
    if len(uploaded_files) > MAX_FILES:
        return error(f"최대 {MAX_FILES}개 파일까지 업로드할 수 있습니다.")
    frames, total_bytes, total_rows = [], 0, 0
    has_station_column = []
    for file in uploaded_files:
        file.seek(0)
        raw = file.read(MAX_FILE_BYTES + 1)
        total_bytes += len(raw)
        if len(raw) > MAX_FILE_BYTES or total_bytes > MAX_TOTAL_BYTES:
            return error("CSV 용량은 파일당 10MB, 합계 32MB 이하여야 합니다.")
        text = None
        for encoding in ('utf-8-sig', 'cp949', 'euc-kr'):
            try:
                text = raw.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            return error("CSV 인코딩을 인식할 수 없습니다 (UTF-8 또는 EUC-KR 필요).")
        try:
            header = next(csv.reader(io.StringIO(text)), [])
            if len(header) > 128 or len(header) != len(set(header)):
                return error("CSV 열은 중복 없이 최대 128개까지 허용됩니다.")
            # 문자열로 읽어 지점번호·품질 플래그를 손실 없이 검사한다.
            frame = pd.read_csv(io.StringIO(text), dtype=str, nrows=MAX_ROWS + 1)
        except (ValueError, csv.Error, pd.errors.ParserError):
            return error("CSV 형식을 읽을 수 없습니다.")
        total_rows += len(frame)
        if total_rows > MAX_ROWS:
            return error(f"전체 자료는 최대 {MAX_ROWS:,}행까지 허용됩니다.")
        wd_cols = [c for c in frame if '풍향' in c and not any(k in c for k in ('최대', '순간', '돌풍', '플래그', 'QC'))]
        ws_cols = [c for c in frame if '풍속' in c and not any(k in c for k in ('최대', '순간', '돌풍', '플래그', 'QC'))]
        dt_cols = [c for c in frame if '일시' in c or '날짜' in c]
        if len(wd_cols) != 1 or len(ws_cols) != 1 or len(dt_cols) != 1:
            return error("파일마다 일시·평균 풍향·평균 풍속 열이 각각 하나 필요합니다.")
        wd_col, ws_col = wd_cols[0], ws_cols[0]
        if '16' in wd_col or not any(unit in wd_col.lower() for unit in ('deg', '°', '도')):
            return error("풍향은 각도(deg) 자료만 지원합니다. 16방위 자료는 사용할 수 없습니다.")
        if 'm/s' not in ws_col.lower().replace(' ', ''):
            return error("풍속 열의 단위가 m/s인지 확인하세요.")
        normalized = frame.rename(columns={dt_cols[0]: 'tm', wd_col: 'wd', ws_col: 'ws'})
        station_cols = [c for c in frame if c in ('지점', '지점번호', 'stnId')]
        if len(station_cols) > 1:
            return error("지점번호 열은 하나만 포함해야 합니다.")
        has_station_column.append(bool(station_cols))
        if station_cols:
            normalized = normalized.rename(columns={station_cols[0]: 'stnId'})
        for label, canonical in (('풍향', 'wdQcflg'), ('풍속', 'wsQcflg')):
            flags = [c for c in frame if label in c and ('플래그' in c or 'QC' in c)]
            if len(flags) > 1:
                return error("품질검사 플래그 열이 중복되었습니다.")
            if flags:
                normalized = normalized.rename(columns={flags[0]: canonical})
        keep = ['tm', 'wd', 'ws'] + [c for c in ('stnId', 'wdQcflg', 'wsQcflg') if c in normalized]
        if not normalized.columns.is_unique:
            return error("표준 열 이름과 충돌하는 중복 열이 있습니다.")
        frames.append(normalized[keep])
    if len(frames) > 1 and not all(has_station_column):
        return error("복수 파일 병합에는 모든 파일에 동일한 지점번호 열이 필요합니다.")
    try:
        valid, invalid = prepare_observations(pd.concat(frames, ignore_index=True), start_date, end_date)
    except ValueError as exc:
        return error(str(exc))
    if valid.empty:
        return error("선택한 기간에 분석 가능한 유효 시간자료가 없습니다.")
    return valid, invalid, len(valid), (valid['tm'].min().date(), valid['tm'].max().date())


def safe_excel_frame(frame):
    """업로드된 문자열이 Excel 수식 또는 외부 링크로 해석되지 않도록 한다."""
    def escape(value):
        if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')):
            return "'" + value
        return value
    return frame.map(escape).rename(columns=escape)


def coverage_summary(frame, start_date, end_date):
    expected = ((end_date - start_date).days + 1) * 24
    valid = frame['tm'].dropna().nunique()
    return {'expected': expected, 'valid': valid, 'missing': max(0, expected - valid),
            'percent': valid / expected * 100 if expected else 0.0}
