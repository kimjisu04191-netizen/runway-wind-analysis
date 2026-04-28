import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px
import time
from datetime import datetime, date, timedelta
from calendar import monthrange
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 1. 페이지 설정
st.set_page_config(page_title="활주로 분석기 V2.8 (병렬 수집)", layout="wide")
st.title("✈️ 활주로 이용률 정밀 분석 (병렬 수집으로 속도 개선)")

# --- [내장 데이터] 광역시도 → (ASOS 종관 / AWS 방재) 관측소 계층 ---
# ASOS: 기상청 종관기상관측망 전체 (94개소) — AsosHourlyInfoService API로 시간자료 제공
ASOS_BY_REGION = {
    "서울": [
        ("108", "서울", "1907-10-01"),
    ],
    "인천": [
        ("112", "인천", "1904-08-01"),
        ("102", "백령도", "2000-01-01"),
        ("201", "강화", "1972-01-01"),
    ],
    "경기": [
        ("98", "동두천", "1998-02-01"),
        ("99", "파주", "2001-12-01"),
        ("119", "수원", "1964-01-01"),
        ("202", "양평", "1972-01-01"),
        ("203", "이천", "1972-01-01"),
    ],
    "강원": [
        ("90", "속초", "1968-01-01"),
        ("93", "북춘천", "2016-10-01"),
        ("95", "철원", "1988-01-01"),
        ("100", "대관령", "1971-12-01"),
        ("101", "춘천", "1966-01-01"),
        ("104", "북강릉", "2008-10-01"),
        ("105", "강릉", "1911-10-01"),
        ("114", "원주", "1971-01-01"),
        ("121", "영월", "1994-01-01"),
        ("211", "인제", "1972-01-01"),
        ("212", "홍천", "1972-01-01"),
        ("216", "태백", "1985-01-01"),
        ("217", "정선군", "2010-01-01"),
    ],
    "충북": [
        ("127", "충주", "1972-01-01"),
        ("131", "청주", "1967-01-01"),
        ("221", "제천", "1972-01-01"),
        ("226", "보은", "1972-01-01"),
    ],
    "대전": [
        ("133", "대전", "1969-01-01"),
    ],
    "세종": [
        ("239", "세종", "2019-10-01"),
    ],
    "충남": [
        ("129", "서산", "1968-01-01"),
        ("232", "천안", "1972-01-01"),
        ("235", "보령", "1972-01-01"),
        ("236", "부여", "1972-01-01"),
        ("238", "금산", "1972-01-01"),
    ],
    "전북": [
        ("140", "군산", "1968-01-01"),
        ("146", "전주", "1918-01-01"),
        ("172", "고창", "2010-12-01"),
        ("243", "부안", "1972-01-01"),
        ("244", "임실", "1972-01-01"),
        ("245", "정읍", "1972-01-01"),
        ("247", "남원", "1972-01-01"),
        ("248", "장수", "1972-01-01"),
        ("251", "고창군", "2010-01-01"),
        ("254", "순창군", "2010-01-01"),
    ],
    "광주": [
        ("156", "광주", "1938-10-01"),
    ],
    "전남": [
        ("165", "목포", "1904-04-01"),
        ("168", "여수", "1942-02-01"),
        ("169", "흑산도", "1997-01-01"),
        ("170", "완도", "1971-01-01"),
        ("174", "순천", "1973-01-01"),
        ("177", "진도(첨찰산)", "2012-01-01"),
        ("252", "영광군", "2010-01-01"),
        ("258", "보성군", "2010-01-01"),
        ("259", "강진군", "2009-12-01"),
        ("260", "장흥", "1972-01-01"),
        ("261", "해남", "2010-05-01"),
        ("262", "고흥", "1972-01-01"),
        ("266", "광양시", "2010-01-01"),
        ("268", "진도군", "2009-12-01"),
    ],
    "대구": [
        ("143", "대구", "1907-01-01"),
    ],
    "경북": [
        ("115", "울릉도", "1938-08-01"),
        ("130", "울진", "1971-01-01"),
        ("135", "추풍령", "1935-01-01"),
        ("136", "안동", "1973-01-01"),
        ("137", "상주", "2002-01-01"),
        ("138", "포항", "1943-01-01"),
        ("271", "봉화", "1988-01-01"),
        ("272", "영주", "1972-01-01"),
        ("273", "문경", "1973-01-01"),
        ("276", "청송군", "2010-01-01"),
        ("277", "영덕", "1972-01-01"),
        ("278", "의성", "1973-01-01"),
        ("279", "구미", "1973-01-01"),
        ("281", "영천", "1972-01-01"),
        ("283", "경주시", "2010-01-01"),
    ],
    "부산": [
        ("159", "부산", "1904-04-01"),
    ],
    "울산": [
        ("152", "울산", "1931-01-01"),
    ],
    "경남": [
        ("155", "창원", "1985-01-01"),
        ("162", "통영", "1968-01-01"),
        ("192", "진주", "1969-01-01"),
        ("253", "김해시", "2010-01-01"),
        ("255", "북창원", "2010-01-01"),
        ("257", "양산시", "2010-01-01"),
        ("263", "의령군", "2010-01-01"),
        ("264", "함양군", "2010-01-01"),
        ("284", "거창", "1972-01-01"),
        ("285", "합천", "1973-01-01"),
        ("288", "밀양", "1973-01-01"),
        ("289", "산청", "1973-01-01"),
        ("294", "거제", "1972-01-01"),
        ("295", "남해", "1972-01-01"),
    ],
    "제주": [
        ("184", "제주", "1923-05-01"),
        ("185", "고산", "1988-01-01"),
        ("188", "성산", "1973-01-01"),
        ("189", "서귀포", "1961-01-01"),
    ],
}

# AWS: 방재기상관측소 주요 관측소 (공항·해안·도심 중심, 분자료 API 집계 대상)
# ※ 공공 API는 분자료(1분)만 제공 → 시간 평균 집계 필요. 호출량 많고 속도 저하 주의.
AWS_BY_REGION = {
    "서울": [
        ("400", "강남"), ("401", "서초"), ("402", "강동"), ("403", "송파"),
        ("404", "강서"), ("410", "관악"), ("411", "영등포"), ("412", "은평"),
        ("413", "마포"), ("421", "성북"), ("423", "중랑"), ("424", "동대문"),
        ("509", "기상청"),
    ],
    "인천": [
        ("549", "공항"), ("551", "강화"), ("552", "영종"), ("553", "인천송도"),
        ("554", "백령도"), ("627", "인천"),
    ],
    "경기": [
        ("517", "과천"), ("518", "광명"), ("519", "부천"), ("520", "시흥"),
        ("521", "김포"), ("546", "안양"), ("555", "의왕"), ("556", "군포"),
        ("557", "안산"), ("571", "수원"), ("572", "평택"), ("573", "화성"),
        ("574", "용인"), ("591", "성남"), ("592", "하남"), ("593", "구리"),
    ],
    "강원": [
        ("523", "춘천"), ("524", "홍천"), ("525", "강릉"), ("527", "평창"),
        ("528", "영월"), ("529", "태백"), ("530", "정선"), ("531", "삼척"),
        ("532", "속초"), ("540", "화천"), ("541", "양구"), ("542", "인제"),
    ],
    "충북": [
        ("533", "청주"), ("534", "충주"), ("535", "제천"), ("558", "음성"),
        ("559", "진천"),
    ],
    "대전": [
        ("647", "대전"),
    ],
    "세종": [
        ("648", "세종"),
    ],
    "충남": [
        ("536", "천안"), ("537", "아산"), ("538", "서산"), ("539", "당진"),
        ("655", "공주"), ("656", "논산"), ("657", "부여"), ("658", "금산"),
    ],
    "전북": [
        ("561", "전주"), ("562", "군산"), ("563", "김제"), ("564", "정읍"),
        ("565", "남원"), ("566", "무주"),
    ],
    "광주": [
        ("672", "광주"),
    ],
    "전남": [
        ("567", "목포"), ("568", "여수"), ("569", "순천"), ("570", "광양"),
        ("578", "해남"), ("579", "완도"), ("580", "진도"), ("581", "흑산도"),
        ("692", "무안공항"),
    ],
    "대구": [
        ("143", "대구"), ("860", "대구수성"), ("861", "대구달서"),
    ],
    "경북": [
        ("743", "포항"), ("744", "경주"), ("745", "안동"), ("746", "구미"),
        ("748", "영주"), ("756", "울릉"), ("788", "포항공항"),
    ],
    "부산": [
        ("900", "부산"), ("904", "부산북항"), ("910", "기장"),
    ],
    "울산": [
        ("152", "울산"), ("932", "울산북구"),
    ],
    "경남": [
        ("788", "사천공항"), ("904", "김해공항"), ("931", "진주"),
        ("932", "창원"), ("933", "통영"), ("934", "거제"),
    ],
    "제주": [
        ("184", "제주"), ("185", "고산"), ("188", "성산"), ("189", "서귀포"),
        ("781", "제주공항"), ("782", "성산공항"),
    ],
}

# 플랫 조회용 (id → (type, name, region, start_date))
def _build_lookup():
    lk = {}
    for region, lst in ASOS_BY_REGION.items():
        for sid, name, start in lst:
            lk.setdefault(sid, ("ASOS", name, region, start))
    for region, lst in AWS_BY_REGION.items():
        for tup in lst:
            sid, name = tup[0], tup[1]
            # ASOS와 ID 충돌 시 ASOS 우선
            if sid not in lk:
                lk[sid] = ("AWS", name, region, "2000-01-01")
    return lk

STATION_LOOKUP = _build_lookup()
# 역호환: STATION_DB 이름 유지 (id → [name, start])
STATION_DB = {sid: [v[1], v[3]] for sid, v in STATION_LOOKUP.items()}

API_URL = "http://apis.data.go.kr/1360000/AsosHourlyInfoService/getWthrDataList"
MAX_WORKERS = 8          # 병렬 요청 수 (공공데이터 포털 권장 범위 내)
REQUEST_TIMEOUT = 20     # 단건 타임아웃
MAX_RETRIES = 3

def _make_session():
    """Keep-Alive + 자동 재시도 세션. 커넥션 풀링으로 TCP/TLS 핸드쉐이크 비용 절감."""
    s = requests.Session()
    retry = Retry(
        total=MAX_RETRIES,
        backoff_factor=0.5,           # 0.5s, 1s, 2s ...
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(pool_connections=MAX_WORKERS, pool_maxsize=MAX_WORKERS, max_retries=retry)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    return s

def _month_chunks(s_date, e_date):
    """분석 기간을 '월 단위'로 쪼개어 [(startDt, endDt), ...] 반환.
    1개월 ≈ 720행 → numOfRows=999 한 페이지에 수렴하므로 페이지네이션 불필요."""
    chunks = []
    cur = date(s_date.year, s_date.month, 1)
    while cur <= e_date:
        last_day = monthrange(cur.year, cur.month)[1]
        m_start = max(cur, s_date)
        m_end = min(date(cur.year, cur.month, last_day), e_date)
        chunks.append((m_start.strftime("%Y%m%d"), m_end.strftime("%Y%m%d")))
        # 다음 달 1일로 이동
        cur = (date(cur.year + (cur.month // 12), ((cur.month % 12) + 1), 1))
    return chunks

def _fetch_one(session, key, stn, start_dt, end_dt):
    """월 단위 1회 요청. 월 > 999행 대비 페이지네이션 포함(안전장치)."""
    items_all = []
    for page in range(1, 4):  # 월 단위는 거의 1페이지로 끝나지만 안전하게 3페이지까지
        params = {
            'serviceKey': key, 'pageNo': str(page), 'numOfRows': '999',
            'dataType': 'JSON', 'dataCd': 'ASOS', 'dateCd': 'HR',
            'startDt': start_dt, 'startHh': '01',
            'endDt': end_dt, 'endHh': '23', 'stnIds': stn,
        }
        r = session.get(API_URL, params=params, timeout=REQUEST_TIMEOUT)
        res = r.json()
        items = res.get('response', {}).get('body', {}).get('items', {}).get('item', [])
        if isinstance(items, dict):
            items = [items]
        if not items:
            break
        items_all.extend(items)
        if len(items) < 999:
            break
    return items_all

# --- [캐시 데이터] 월별 병렬 수집 함수 ---
@st.cache_data(show_spinner=False)
def get_weather_data_v28(key, stn, s_date, e_date):
    chunks = _month_chunks(s_date, e_date)
    total = len(chunks)
    if total == 0:
        return None, "날짜 범위가 비어 있습니다."

    msg_slot = st.empty()
    p_bar = st.progress(0)
    msg_slot.info(f"⏳ {total}개월 데이터 병렬 수집 중... (동시 요청 {MAX_WORKERS}건)")

    all_combined = []
    done = 0
    t0 = time.perf_counter()

    with _make_session() as session, ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(_fetch_one, session, key, stn, s, e): (s, e) for s, e in chunks}
        for fut in as_completed(futures):
            s, e = futures[fut]
            try:
                items = fut.result()
                if items:
                    all_combined.extend(items)
            except Exception as ex:
                return None, f"{s}~{e} 구간 수집 실패: {ex}"
            done += 1
            p_bar.progress(done / total)
            msg_slot.info(f"⏳ 수집 진행 {done}/{total}개월 · 경과 {time.perf_counter()-t0:.1f}s")

    msg_slot.success(f"✅ 수집 완료 · {len(all_combined):,}행 · 총 {time.perf_counter()-t0:.1f}s")

    if not all_combined:
        return None, "수집된 데이터가 없습니다. 날짜와 지점을 확인하세요."

    df = pd.DataFrame(all_combined)
    df['wd'] = pd.to_numeric(df['wd'], errors='coerce')
    df['ws_kt'] = pd.to_numeric(df['ws'], errors='coerce') * 1.94384
    df = df.dropna(subset=['wd', 'ws_kt'])
    # 관측 시각 기준 중복 제거(병렬 중복 방어)
    if 'tm' in df.columns:
        df = df.drop_duplicates(subset=['tm'])
    return df, len(df)

# --- [ICAO/논문 기반 분석 함수] ---
# 논문: 신동진, 김도현 (2009) "활주로 방향설정을 위한 풍배도 프로그램의 개발 연구"
# 기준: ICAO Annex 14 / Doc. 9157 Airport Design Manual Part 1

CROSSWIND_LIMITS_KT = [10, 13, 20]   # ICAO Doc. 9157 Table 1
CALM_THRESHOLD_KT = 3.0              # 논문 §3.2 '무영향 데이터' 0~3 knots
USABILITY_TARGET = 95.0              # ICAO 권고 최소 이용률
TIE_TOLERANCE = 0.01                 # 동율 판정 허용오차 (%)
MIN_SEPARATION_DEG = 30              # 2개 활주로 최소 각도 분리 (물리적 배치 제약)

def select_limit_by_rwy_length(length_m, low_friction=False):
    """ICAO Doc. 9157 Table 1 기반 측풍 허용치 자동 선택."""
    if length_m >= 1500:
        if low_friction:
            return 13, "≥1,500m · 종방향 마찰계수 부족 → 13 kt"
        return 20, "≥1,500m → 20 kt"
    if length_m >= 1200:
        return 13, "1,200~1,500m → 13 kt"
    return 10, "<1,200m → 10 kt"

def rwy_name(deg):
    """방위각(0~179°)을 활주로 명칭(예: '15-33')으로 변환."""
    def fmt(d):
        n = round(d / 10) % 36
        return 36 if n == 0 else n
    a = fmt(deg)
    b = fmt((deg + 180) % 360)
    lo, hi = (a, b) if a < b else (b, a)
    return f"{lo:02d}-{hi:02d}"

def analyze_runway(df):
    """전체 분석: calm 처리 + 3개 허용치 + 동율 처리 + 2개 활주로 + 빈도표."""
    ws = df['ws_kt'].to_numpy(dtype=np.float32)
    wd = df['wd'].to_numpy(dtype=np.float32)
    N_total = len(ws)

    # 1) Calm(무영향) 분리 — 논문 §3.2
    calm_mask = ws <= CALM_THRESHOLD_KT
    N_calm = int(calm_mask.sum())
    eff_ws = ws[~calm_mask]
    eff_wd = wd[~calm_mask]
    N_eff = len(eff_ws)

    # 2) 유효 바람에 대한 측풍 행렬 (N_eff × 180)
    angles = np.arange(0, 180, dtype=np.int32)
    diff = np.radians(eff_wd[:, None] - angles[None, :])
    xwind = np.abs(eff_ws[:, None] * np.sin(diff)).astype(np.float32)  # |측풍|, knots

    results = {}
    for limit in CROSSWIND_LIMITS_KT:
        coverage = xwind <= limit                # (N_eff, 180) bool
        eff_covered = coverage.sum(axis=0)       # (180,)
        # 이용률 = (calm + 유효_허용측풍 이내) / 전체
        usab = (N_calm + eff_covered) / N_total * 100.0

        # 3) 동율(Tie-breaking) — 논문 §3.2
        u_max = float(usab.max())
        tied = np.where(usab >= u_max - TIE_TOLERANCE)[0]
        mean_xw_tied = xwind[:, tied].mean(axis=0)
        best_angle = int(tied[int(np.argmin(mean_xw_tied))])

        # 5) 2개 활주로 분석 (합집합 이용률)
        # |A∪B| = |A| + |B| - |A∩B|, 행렬곱으로 벡터화
        Cf = coverage.astype(np.float32)
        inter = Cf.T @ Cf                                       # (180,180)
        union = eff_covered[:, None] + eff_covered[None, :] - inter
        pair_usab = (N_calm + union) / N_total * 100.0          # (180,180)
        sep = np.abs(angles[:, None] - angles[None, :])
        sep_ok = (sep >= MIN_SEPARATION_DEG) & (sep <= 180 - MIN_SEPARATION_DEG)
        masked = np.where(sep_ok, pair_usab, -1.0)
        flat = int(np.argmax(masked))
        i, j = int(flat // 180), int(flat % 180)
        pair_best_u = float(pair_usab[i, j])

        results[limit] = {
            'usability': usab,
            'best_angle': best_angle,
            'best_usab': u_max,
            'tied_count': len(tied),
            'mean_xwind': float(xwind[:, best_angle].mean()),
            'max_xwind': float(xwind[:, best_angle].max()),
            'pass': u_max >= USABILITY_TARGET,
            'pair_angles': (min(i, j), max(i, j)),
            'pair_usab': pair_best_u,
            'pair_pass': pair_best_u >= USABILITY_TARGET,
        }

    # 6) 16방위 × 풍속 빈도표 — 논문 Table 6
    freq_table = _build_freq_table(wd, ws, N_total)

    return {
        'N_total': N_total, 'N_calm': N_calm, 'N_eff': N_eff,
        'calm_pct': N_calm / N_total * 100.0,
        'angles': angles, 'results': results, 'freq_table': freq_table,
    }

def _build_freq_table(wd, ws, N_total):
    """16방위 × 5개 풍속구간 빈도표(%). 논문 Table 6 한국어 단위(노트) 버전."""
    dir_names = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                 "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    speed_bins = [(0, 3), (4, 10), (11, 13), (14, 20), (21, 9999)]
    speed_labels = ["Calm 0–3 kt", "4–10 kt", "11–13 kt", "14–20 kt", ">20 kt"]
    # 22.5° 간격, 첫 섹터 N은 348.75°~11.25° 중심
    dir_idx = (((wd + 11.25) // 22.5) % 16).astype(np.int32)
    table = np.zeros((16, len(speed_bins)), dtype=np.float64)
    for d in range(16):
        for s, (lo, hi) in enumerate(speed_bins):
            table[d, s] = ((dir_idx == d) & (ws >= lo) & (ws <= hi)).sum()
    pct = table / N_total * 100.0
    df_out = pd.DataFrame(pct, index=dir_names, columns=speed_labels).round(2)
    df_out['TOTAL %'] = df_out.sum(axis=1).round(2)
    return df_out

# 2. 사이드바 UI
st.sidebar.header("📋 분석 설정")
api_key = st.sidebar.text_input("1. API Key (Decoding)", type="password")

st.sidebar.markdown("#### 2. 관측소 선택")
obs_type = st.sidebar.radio(
    "관측종류",
    ["ASOS (종관)", "AWS (방재·실험적)"],
    horizontal=True,
    help="ASOS는 시간자료 직접 제공. AWS는 분자료를 시간 평균으로 집계 (호출량 많고 느림).",
)
is_asos = obs_type.startswith("ASOS")
region_db = ASOS_BY_REGION if is_asos else AWS_BY_REGION
region_list = list(region_db.keys())
default_region_idx = region_list.index("전남") if "전남" in region_list else 0
region = st.sidebar.selectbox("광역시도", region_list, index=default_region_idx)

# 해당 광역시도의 관측소 목록
stations_in_region = region_db[region]
if is_asos:
    stn_labels = [f"{name} ({sid}) · {start}" for sid, name, start in stations_in_region]
    default_name = "목포" if region == "전남" else stations_in_region[0][1]
    default_idx = next((i for i, s in enumerate(stations_in_region) if s[1] == default_name), 0)
else:
    stn_labels = [f"{name} ({sid})" for sid, name in stations_in_region]
    default_idx = 0

selected_idx = st.sidebar.selectbox("관측소", range(len(stn_labels)),
                                    format_func=lambda i: stn_labels[i],
                                    index=default_idx)
sel = stations_in_region[selected_idx]
stn_id = sel[0]
stn_name = sel[1]
stn_start = sel[2] if is_asos else "—"

if is_asos:
    st.sidebar.success(f"📌 [ASOS] {stn_name} ({region}) · 관측 가능일: {stn_start} ~ 현재")
else:
    st.sidebar.warning(
        f"⚠️ [AWS] {stn_name} ({region}) — 분자료 집계 방식. "
        f"현재 앱은 ASOS 시간자료 API 전용이므로, AWS 분석은 추후 업데이트 예정입니다. "
        f"가장 가까운 ASOS 관측소를 사용해 주세요."
    )

st.sidebar.markdown("---")
st.sidebar.markdown("#### 분석 기간")
preset = st.sidebar.radio(
    "기간 설정", ["최근 10년", "최근 5년", "사용자 지정"],
    horizontal=True,
    help="ICAO Annex 14 권고: 최소 5년 이상의 신뢰성 있는 기상통계자료",
)

# 종료월 = 오늘 기준 직전(완료된) 월 — 진행 중 월은 제외
_today = date.today()
_end_y, _end_m = (_today.year - 1, 12) if _today.month == 1 else (_today.year, _today.month - 1)

def _months_back(ey, em, n_years):
    """종료월 포함 정확히 (n_years × 12)개월이 되는 시작 연/월."""
    idx = ey * 12 + (em - 1) - (n_years * 12 - 1)
    return idx // 12, (idx % 12) + 1

if preset == "최근 10년":
    start_y, start_m = _months_back(_end_y, _end_m, 10)
    end_y, end_m = _end_y, _end_m
elif preset == "최근 5년":
    start_y, start_m = _months_back(_end_y, _end_m, 5)
    end_y, end_m = _end_y, _end_m
else:  # 사용자 지정
    # 선택된 관측소 관측 시작년도 이후만 허용
    try:
        stn_start_yr = int(stn_start.split("-")[0]) if stn_start and stn_start != "—" else 1960
    except Exception:
        stn_start_yr = 1960
    yr_range = list(range(max(1960, stn_start_yr), _today.year + 1))
    mo_range = list(range(1, 13))

    cA, cB = st.sidebar.columns(2)
    with cA:
        default_start_y = max(yr_range[0], _today.year - 5)
        start_y = st.selectbox("시작 연", yr_range,
                               index=yr_range.index(default_start_y) if default_start_y in yr_range else 0)
        start_m = st.selectbox("시작 월", mo_range, index=0)
    with cB:
        end_y = st.selectbox("종료 연", yr_range, index=len(yr_range) - 1)
        end_m = st.selectbox("종료 월", mo_range, index=_end_m - 1)

# 날짜 객체 변환 (종료월은 말일)
start_date = date(start_y, start_m, 1)
_last_day = monthrange(end_y, end_m)[1]
end_date = date(end_y, end_m, _last_day)

# 유효성 및 요약
_months = (end_y - start_y) * 12 + (end_m - start_m) + 1
if start_date > end_date:
    st.sidebar.error("⚠️ 시작이 종료보다 늦습니다.")
elif _months < 60:
    st.sidebar.warning(f"⚠️ {_months}개월 (<5년) — ICAO 권고 기간 미달")
    st.sidebar.caption(f"📅 {start_date:%Y-%m} ~ {end_date:%Y-%m} · {_months}개월")
else:
    st.sidebar.success(f"📅 {start_date:%Y-%m} ~ {end_date:%Y-%m} · {_months}개월 ({_months/12:.1f}년)")

st.sidebar.markdown("#### 3. 측풍 허용치 (ICAO Doc. 9157)")
rwy_length = st.sidebar.number_input("활주로 길이 (m)", min_value=300, max_value=5000, value=2000, step=100)
low_friction = st.sidebar.checkbox("종방향 마찰계수 부족 (활주로 제동효과 불량)", value=False)
auto_limit, auto_note = select_limit_by_rwy_length(rwy_length, low_friction)
st.sidebar.info(f"🎯 자동 선택: **{auto_limit} kt** · {auto_note}")
override = st.sidebar.checkbox("수동 선택 사용", value=False)
if override:
    primary_limit = st.sidebar.selectbox("측풍 허용치 (Knot)", CROSSWIND_LIMITS_KT,
                                         index=CROSSWIND_LIMITS_KT.index(auto_limit))
else:
    primary_limit = auto_limit

if st.sidebar.button("🧹 데이터 캐시 삭제"):
    st.cache_data.clear()
    st.sidebar.info("캐시가 삭제되었습니다.")

# 3. 분석 실행
if st.sidebar.button("🚀 분석 시작"):
    if not api_key:
        st.error("API Key를 입력하세요.")
    elif not is_asos:
        st.error(
            f"❌ AWS(방재) 관측소 **{stn_name}** 는 현재 분석 대상이 아닙니다.\n\n"
            f"공공데이터포털 KMA API에서 AWS는 **분(分)자료만** 제공하므로, "
            f"시간 단위 분석을 위해서는 60배 호출량과 풍향 벡터 평균 집계 로직이 필요합니다.\n\n"
            f"해결 방법: 사이드바에서 **ASOS (종관)** 로 전환 후 **{region}** 지역의 인접 관측소를 선택하세요."
        )
    else:
        df, result = get_weather_data_v28(api_key, stn_id, start_date, end_date)

        if df is None:
            st.error(f"❌ 분석 실패: {result}")
        else:
            st.success(f"✅ {stn_name} · {result:,}시간 데이터 수집 완료")
            with st.spinner("📊 바람성분 vector 분석 중..."):
                A = analyze_runway(df)

            # --- 데이터 요약 ---
            st.divider()
            s1, s2, s3, s4 = st.columns(4)
            s1.metric("전체 관측 시간", f"{A['N_total']:,} h")
            s2.metric("Calm (0~3 kt)", f"{A['N_calm']:,} h", f"{A['calm_pct']:.2f}%")
            s3.metric("유효 데이터", f"{A['N_eff']:,} h")
            s4.metric("적용 측풍 허용치", f"{primary_limit} kt")
            st.caption("※ Calm(무영향) 데이터는 논문 §3.2에 따라 활주로 방향 무관하게 '이용 가능'으로 집계됩니다.")

            # --- 주 결과(자동/수동 선택된 한계치) ---
            st.subheader(f"🎯 분석 결과 · 허용치 {primary_limit} kt")
            r = A['results'][primary_limit]
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("최적 활주로", rwy_name(r['best_angle']), f"{r['best_angle']}°")
            c2.metric("최대 이용률", f"{r['best_usab']:.3f}%",
                      "✅ PASS" if r['pass'] else "❌ FAIL")
            c3.metric("평균 측풍", f"{r['mean_xwind']:.2f} kt")
            c4.metric("동율 후보", f"{r['tied_count']}개",
                      "동율 처리 적용" if r['tied_count'] > 1 else "유일")

            if not r['pass']:
                st.warning(
                    f"⚠️ 단일 활주로로 95% 미달. 2개 활주로 최적 조합: "
                    f"**{rwy_name(r['pair_angles'][0])} + {rwy_name(r['pair_angles'][1])}** "
                    f"→ 이용률 **{r['pair_usab']:.3f}%** "
                    f"{'✅ PASS' if r['pair_pass'] else '❌ 여전히 FAIL'}"
                )

            # --- 탭 ---
            t1, t2, t3, t4, t5, t6 = st.tabs([
                "📊 3개 허용치 종합", "📈 이용률 곡선", "🌀 바람장미",
                "📋 16방위 빈도표", "🛬 2개 활주로 분석", "📐 방위각 상세표"
            ])

            with t1:
                st.markdown("#### ICAO Doc. 9157 세 개 측풍 한계치 동시 분석")
                summary_rows = []
                for lim in CROSSWIND_LIMITS_KT:
                    rr = A['results'][lim]
                    summary_rows.append({
                        "허용치": f"{lim} kt",
                        "최적 활주로": rwy_name(rr['best_angle']),
                        "방위각 (°)": rr['best_angle'],
                        "이용률 (%)": round(rr['best_usab'], 3),
                        "평균 측풍 (kt)": round(rr['mean_xwind'], 2),
                        "최대 측풍 (kt)": round(rr['max_xwind'], 2),
                        "동율 후보수": rr['tied_count'],
                        "단일 판정": "✅ PASS" if rr['pass'] else "❌ FAIL",
                        "2개 조합 이용률 (%)": round(rr['pair_usab'], 3),
                        "2개 조합": f"{rwy_name(rr['pair_angles'][0])} + {rwy_name(rr['pair_angles'][1])}",
                    })
                st.dataframe(pd.DataFrame(summary_rows), width='stretch', hide_index=True)

            with t2:
                curve_df = pd.DataFrame({
                    "angle": np.tile(A['angles'], len(CROSSWIND_LIMITS_KT)),
                    "usability": np.concatenate([A['results'][l]['usability'] for l in CROSSWIND_LIMITS_KT]),
                    "limit_kt": np.repeat([f"{l} kt" for l in CROSSWIND_LIMITS_KT], len(A['angles'])),
                })
                fig1 = px.line(curve_df, x="angle", y="usability", color="limit_kt",
                               title="방향별 이용률 (허용치별 비교)",
                               labels={"angle": "활주로 방위각 (°)", "usability": "이용률 (%)"})
                fig1.add_hline(y=USABILITY_TARGET, line_dash="dash", line_color="red",
                               annotation_text="ICAO 95%", annotation_position="top right")
                for lim in CROSSWIND_LIMITS_KT:
                    rr = A['results'][lim]
                    fig1.add_vline(x=rr['best_angle'], line_dash="dot", opacity=0.3)
                st.plotly_chart(fig1, width='stretch')

            with t3:
                fig2 = px.bar_polar(df, r="ws_kt", theta="wd", color="ws_kt",
                                    title="Wind Rose (풍향/풍속 분포)",
                                    color_continuous_scale=px.colors.sequential.Plasma)
                st.plotly_chart(fig2, width='stretch')

            with t4:
                st.markdown("#### 16방위 × 풍속구간 빈도표 (%) — 논문 Table 6 양식")
                st.dataframe(A['freq_table'], width='stretch')
                st.caption(f"합계 100% 기준 · Calm(0~3 kt) 비율: {A['calm_pct']:.2f}%")

            with t5:
                st.markdown(f"#### 2개 활주로 최적 조합 (허용치 {primary_limit} kt)")
                st.caption(f"※ 최소 각도 분리 {MIN_SEPARATION_DEG}° 제약 적용 "
                           f"(물리적 배치 가능성 고려)")
                r = A['results'][primary_limit]
                p1, p2 = r['pair_angles']
                d1, d2, d3 = st.columns(3)
                d1.metric("1차 활주로", rwy_name(p1), f"{p1}°")
                d2.metric("2차 활주로", rwy_name(p2), f"{p2}°")
                d3.metric("조합 이용률", f"{r['pair_usab']:.3f}%",
                          "✅ PASS" if r['pair_pass'] else "❌ FAIL")
                st.info(
                    f"단일 활주로 최대 이용률: **{r['best_usab']:.3f}%** → "
                    f"2개 조합 이용률: **{r['pair_usab']:.3f}%** "
                    f"(개선 +{r['pair_usab']-r['best_usab']:.3f}%p)"
                )

            with t6:
                st.markdown("#### 방위각 간격별 이용률 상세표")
                st.caption("각 행은 활주로 방위(방향 ↔ 대응방향) 쌍이며, 허용측풍별 이용률(%)을 나타냅니다. 95% 미달은 빨강, 이상은 초록으로 강조됩니다.")
                col_a, col_b = st.columns([1, 3])
                with col_a:
                    step = st.selectbox("각도 간격 (°)", [1, 5, 10, 20, 30], index=2, key="step_table")

                headings = np.arange(step, 181, step, dtype=int)   # step, 2·step, ..., ≤180
                rows = []
                for h in headings:
                    i = int(h % 180)                               # 180° ≡ 0° (동일 활주로)
                    rec = int(h + 180)                             # 10→190, ..., 180→360
                    row = {
                        "방향 (°)": int(h),
                        "대응방향 (°)": rec,
                        "활주로": rwy_name(i),
                    }
                    for lim in CROSSWIND_LIMITS_KT:
                        row[f"{lim} kt 이용률 (%)"] = round(float(A['results'][lim]['usability'][i]), 2)
                    rows.append(row)
                df_table = pd.DataFrame(rows)

                # 95% 기준 색상 강조 (pandas 3.x: Styler.map 사용)
                kt_cols = [c for c in df_table.columns if "이용률" in c]
                def _hl(v):
                    if isinstance(v, (int, float)):
                        if v >= USABILITY_TARGET:
                            return "background-color: #d4edda; color: #155724;"
                        return "background-color: #f8d7da; color: #721c24;"
                    return ""
                styled = df_table.style.map(_hl, subset=kt_cols).format({c: "{:.2f}" for c in kt_cols})
                st.dataframe(styled, width='stretch', hide_index=True)

                # 최적 방향 요약
                st.markdown("##### 📌 허용치별 최적 방위각 (표 기준)")
                best_rows = []
                for lim in CROSSWIND_LIMITS_KT:
                    sub = df_table[["방향 (°)", "대응방향 (°)", "활주로", f"{lim} kt 이용률 (%)"]]
                    top = sub.loc[sub[f"{lim} kt 이용률 (%)"].idxmax()]
                    best_rows.append({
                        "허용치": f"{lim} kt",
                        "최적 방향": f"{int(top['방향 (°)'])}° / {int(top['대응방향 (°)'])}°",
                        "활주로": top['활주로'],
                        "이용률 (%)": f"{top[f'{lim} kt 이용률 (%)']:.2f}",
                        "판정": "✅ PASS" if top[f'{lim} kt 이용률 (%)'] >= USABILITY_TARGET else "❌ FAIL",
                    })
                st.dataframe(pd.DataFrame(best_rows), width='stretch', hide_index=True)

                # CSV 다운로드
                csv_bytes = df_table.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
                st.download_button(
                    "💾 CSV 다운로드",
                    csv_bytes,
                    file_name=f"runway_usability_{stn_name}_{start_date}_{end_date}_step{step}.csv",
                    mime="text/csv",
                )
