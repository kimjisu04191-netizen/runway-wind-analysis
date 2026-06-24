import io
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
st.set_page_config(page_title="활주로 이용률 정밀 분석", layout="wide")
st.title("활주로 이용률 정밀 분석")

# 설정 항목이 많아 한눈에 보기 쉽도록 전체 폰트를 약간 축소
st.markdown("""
<style>
.block-container { padding-top: 2rem; font-size: 0.92rem; }
h3 { font-size: 1.05rem !important; }
h4 { font-size: 0.95rem !important; }
div[data-testid="stMetricValue"] { font-size: 1.2rem; }
div[data-testid="stMetricLabel"] { font-size: 0.8rem; }
div[data-testid="stMetricDelta"] { font-size: 0.78rem; }
label[data-testid="stWidgetLabel"] p { font-size: 0.85rem; }
div[data-testid="stExpander"] summary p { font-size: 0.88rem; }
</style>
""", unsafe_allow_html=True)

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

# ※ AWS(방재기상관측) 관측소 목록은 의도적으로 제공하지 않음.
#   - 기상청 API 허브의 공식 관측소 정보 API(stn_inf.php?inf=AWS)는 "활용신청 필요(403)"로 비공개
#   - 검증되지 않은 추정 ID/명칭을 보여주면 사용자에게 혼동을 줄 수 있어 제외함
#   - 더 근본적으로, AWS 시간자료 API(awsh.php)는 "단일 시점 조회"만 지원하고
#     기간(tm1~tm2) 조회는 항상 "최근 약 1개월"만 반환하도록 고정되어 있어
#     5~10년 분석에 필요한 장기 시계열 수집이 구조적으로 불가능함 (아래 사이드바 안내 참고)

# 플랫 조회용 (id → (type, name, region, start_date))
def _build_lookup():
    lk = {}
    for region, lst in ASOS_BY_REGION.items():
        for sid, name, start in lst:
            lk.setdefault(sid, ("ASOS", name, region, start))
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
        return None, None, "날짜 범위가 비어 있습니다."

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

    msg_slot.success(f"수집 완료 · {len(all_combined):,}행 · 총 {time.perf_counter()-t0:.1f}s")

    if not all_combined:
        return None, None, "수집된 데이터가 없습니다. 날짜와 지점을 확인하세요."

    df = pd.DataFrame(all_combined)
    df['wd']    = pd.to_numeric(df['wd'], errors='coerce')
    df['ws_kt'] = pd.to_numeric(df['ws'], errors='coerce') * 1.94384
    # 관측 시각 기준 중복 제거(병렬 중복 방어)
    if 'tm' in df.columns:
        df = df.drop_duplicates(subset=['tm'])
    # ── 유효 / 결측 분리 ──────────────────────────────────────────
    invalid_mask = df['wd'].isna() | df['ws_kt'].isna()
    df_invalid   = df[invalid_mask].reset_index(drop=True)
    df_valid     = df[~invalid_mask].reset_index(drop=True)
    return df_valid, df_invalid, len(df_valid)

# --- [AWS CSV 파싱 함수] ---
def _parse_aws_csv(uploaded_files):
    """기상자료개방포털 방재기상관측 시간자료 CSV 파싱.
    - 인코딩 자동 감지 (UTF-8-sig / EUC-KR / CP949)
    - 복수 파일 병합 지원 (연도별 분할 다운로드 대응)
    - 풍향·풍속 컬럼 자동 탐지
    반환: (df_valid, df_invalid, row_count, (start_date, end_date))
          또는 (None, None, error_msg, (None, None))
    """
    all_dfs = []
    for f in uploaded_files:
        raw = f.read()
        text = None
        for enc in ('utf-8-sig', 'euc-kr', 'cp949', 'utf-8'):
            try:
                text = raw.decode(enc)
                break
            except (UnicodeDecodeError, LookupError):
                continue
        if text is None:
            return None, None, f"'{f.name}' 인코딩 인식 불가 (UTF-8 또는 EUC-KR 파일 필요).", (None, None)
        try:
            tmp = pd.read_csv(io.StringIO(text))
            all_dfs.append(tmp)
        except Exception as e:
            return None, None, f"'{f.name}' CSV 파싱 오류: {e}", (None, None)

    if not all_dfs:
        return None, None, "업로드된 파일이 없습니다.", (None, None)

    df = pd.concat(all_dfs, ignore_index=True)

    # ── 풍향 컬럼 탐지 ────────────────────────────────────────────
    wd_col = next((c for c in df.columns if '풍향' in c), None)
    # 풍속: '최대', '순간', '돌풍' 제외한 첫 번째 풍속 컬럼
    ws_col = next(
        (c for c in df.columns
         if '풍속' in c and all(kw not in c for kw in ['최대', '순간', '돌풍'])),
        None
    )

    if wd_col is None:
        return None, None, f"풍향 컬럼을 찾을 수 없습니다. 전체 컬럼: {list(df.columns)}", (None, None)
    if ws_col is None:
        return None, None, f"풍속 컬럼을 찾을 수 없습니다. 전체 컬럼: {list(df.columns)}", (None, None)

    df['wd']    = pd.to_numeric(df[wd_col], errors='coerce')
    df['ws_kt'] = pd.to_numeric(df[ws_col], errors='coerce') * 1.94384   # m/s → knots

    # ── 날짜 범위 자동 감지 ───────────────────────────────────────
    dt_col = next((c for c in df.columns if '일시' in c or '날짜' in c), None)
    csv_start = csv_end = None
    if dt_col is not None:
        parsed_dt = pd.to_datetime(df[dt_col], errors='coerce').dropna()
        if len(parsed_dt) > 0:
            csv_start = parsed_dt.min().date()
            csv_end   = parsed_dt.max().date()

    # ── 유효 / 결측 분리 ──────────────────────────────────────────
    invalid_mask  = df['wd'].isna() | df['ws_kt'].isna()
    df_invalid    = df[invalid_mask].reset_index(drop=True)
    df_valid      = df[~invalid_mask].reset_index(drop=True)

    if len(df_valid) == 0:
        return None, None, "풍향·풍속 유효 데이터가 없습니다 (모두 결측).", (csv_start, csv_end)

    return df_valid, df_invalid, len(df_valid), (csv_start, csv_end)


# --- [주소 기반 관측소 검색 함수] ---
# 1) 기상청 API 허브 stn_inf.php → ASOS/AWS 관측소 위경도 DB
# 2) 카카오 로컬 API 주소검색    → 입력 주소 → WGS84 위경도 (1회 호출로 완료)
# 3) Haversine                  → 관측소 DB와의 거리 계산 → 최근접 N개

@st.cache_data(show_spinner=False, ttl=86400)
def _load_station_db(auth_key):
    """기상청 API 허브 stn_inf.php로 ASOS(SFC)+AWS 관측소 위경도 DB 구축.
    고정폭 텍스트(EUC-KR) → 바이트 단위 슬라이싱으로 파싱 (한글 폭 깨짐 방지)."""
    base = "https://apihub.kma.go.kr/api/typ01/url/stn_inf.php"
    tm = datetime.now().strftime('%Y%m%d%H%M')

    def _fetch_lines(inf):
        r = requests.get(base, params={'inf': inf, 'stn': '', 'tm': tm, 'help': '0', 'authKey': auth_key}, timeout=15)
        lines = r.content.split(b'\n')
        return [l for l in lines if l.strip() and not l.startswith(b'#')]

    rows = []
    # SFC(종관/ASOS): STN_ID(0:5) LON(5:19) LAT(19:33) ... STN_KO(96:117) ... LAW_ADDR(163:222)
    for line in _fetch_lines('SFC'):
        rows.append({
            'stn_id': line[0:5].decode('euc-kr', errors='replace').strip(),
            'lon':    line[5:19].decode('euc-kr', errors='replace').strip(),
            'lat':    line[19:33].decode('euc-kr', errors='replace').strip(),
            'name_ko': line[96:117].decode('euc-kr', errors='replace').strip(),
            'addr':   line[163:222].decode('euc-kr', errors='replace').strip(),
            'type':   'ASOS',
        })
    # AWS(방재): STN_ID(0:5) LON(5:19) LAT(19:33) ... STN_KO(71:92) ... LAW_ADDR(138:197)
    for line in _fetch_lines('AWS'):
        rows.append({
            'stn_id': line[0:5].decode('euc-kr', errors='replace').strip(),
            'lon':    line[5:19].decode('euc-kr', errors='replace').strip(),
            'lat':    line[19:33].decode('euc-kr', errors='replace').strip(),
            'name_ko': line[71:92].decode('euc-kr', errors='replace').strip(),
            'addr':   line[138:197].decode('euc-kr', errors='replace').strip(),
            'type':   'AWS',
        })

    df = pd.DataFrame(rows)
    df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
    df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
    df = df.dropna(subset=['lon', 'lat']).reset_index(drop=True)
    return df


def _geocode_address_kakao(keyword, kakao_key):
    """카카오 로컬 API 주소검색: 주소 키워드 → WGS84 위경도 1회 호출.
    반환: (lat, lon, display_addr, error_msg)."""
    try:
        r = requests.get(
            "https://dapi.kakao.com/v2/local/search/address.json",
            headers={"Authorization": f"KakaoAK {kakao_key}"},
            params={"query": keyword},
            timeout=10,
        )
        data = r.json()
        if r.status_code != 200:
            return None, None, None, data.get('message', f'HTTP {r.status_code} 오류 (REST API 키를 확인하세요)')
        docs = data.get('documents') or []
        if not docs:
            return None, None, None, "검색된 주소가 없습니다. 더 구체적인 주소를 입력해 보세요."
        d = docs[0]
        lon, lat = float(d['x']), float(d['y'])
        road = d.get('road_address')
        display_addr = road['address_name'] if road else d.get('address_name', keyword)
        return lat, lon, display_addr, None
    except Exception as e:
        return None, None, None, str(e)


def _haversine_km(lat1, lon1, lat2, lon2):
    """두 위경도 좌표 간 대원거리(km)."""
    R = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi, dlambda = np.radians(lat2 - lat1), np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlambda / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


def _nearest_stations(lat, lon, station_df, stn_type, n=3):
    """station_df에서 stn_type('ASOS'/'AWS') 관측소 중 (lat,lon)에 가장 가까운 n개."""
    sub = station_df[station_df['type'] == stn_type].copy()
    sub['dist_km'] = _haversine_km(lat, lon, sub['lat'].to_numpy(), sub['lon'].to_numpy())
    return sub.sort_values('dist_km').head(n).reset_index(drop=True)


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

# --- [개인용 기본값] secrets.toml에 저장된 키를 세션 상태 기본값으로 자동 채움.
#     secrets.toml은 .gitignore 처리되어 GitHub(public repo)에는 절대 올라가지 않음.
def _secret(name, default=""):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default

# API 키는 메인 화면에 직접 노출하지 않고 세션 상태로만 보관 → 팝업(dialog)에서 입력/수정
for _sk, _sname in [("api_key", "ASOS_API_KEY"), ("kma_hub_key", "KMA_HUB_KEY"), ("kakao_key", "KAKAO_REST_KEY")]:
    if _sk not in st.session_state:
        st.session_state[_sk] = _secret(_sname)

@st.dialog("API 키 설정")
def _api_key_dialog():
    st.text_input(
        "ASOS API Key (Decoding)", type="password", key="api_key",
        value=st.session_state.get("api_key", ""),
        help="공공데이터포털(data.go.kr)에서 발급받은 종관기상관측(ASOS) Decoding 키",
    )
    st.text_input(
        "기상청 API 허브 인증키", type="password", key="kma_hub_key",
        value=st.session_state.get("kma_hub_key", ""),
        help="apihub.kma.go.kr에서 발급받은 인증키 (관측소 위경도 조회 및 주소검색용)",
    )
    st.text_input(
        "카카오 REST API 키", type="password", key="kakao_key",
        value=st.session_state.get("kakao_key", ""),
        help="Kakao Developers(developers.kakao.com)에서 앱 생성 후 즉시 발급되는 REST API 키. "
             "별도 승인 대기 없이 바로 사용 가능합니다.",
    )
    st.caption("입력한 값은 이 브라우저 세션에만 유지되며, 코드나 GitHub에는 저장되지 않습니다.")
    if st.button("닫기", type="primary", use_container_width=True):
        st.rerun()

# 2. 메인페이지 설정 UI — 사이드바 대신 첫 화면에서 한 번에 설정 (박스 단위로 구획)
st.markdown("### 분석 설정")

row1_col1, row1_col2 = st.columns(2)

with row1_col1:
    with st.container(border=True):
        st.markdown("**1. 관측소 선택**")
        obs_type = st.radio(
            "관측종류",
            ["ASOS (종관)", "AWS (방재) — CSV 업로드"],
            horizontal=True,
            help=(
                "ASOS: 기간(시작∼종료) 범위 조회 API 제공 → 5∼10년 장기분석 가능.\n"
                "AWS: API는 단일 시점 조회만 지원되어 CSV 업로드 방식으로 분석합니다."
            ),
        )
        is_asos = obs_type.startswith("ASOS")

        aws_files = []   # ASOS 경로에서도 변수가 항상 정의되도록

        if is_asos:
            region_db = ASOS_BY_REGION
            region_list = list(region_db.keys())
            default_region_idx = region_list.index("전남") if "전남" in region_list else 0

            c_region, c_station = st.columns(2)
            with c_region:
                region = st.selectbox("광역시도", region_list, index=default_region_idx)

            # 해당 광역시도의 관측소 목록
            stations_in_region = region_db[region]
            stn_labels = [f"{name} ({sid}) · {start}" for sid, name, start in stations_in_region]
            default_name = "목포" if region == "전남" else stations_in_region[0][1]
            default_idx = next((i for i, s in enumerate(stations_in_region) if s[1] == default_name), 0)

            with c_station:
                selected_idx = st.selectbox("관측소", range(len(stn_labels)),
                                            format_func=lambda i: stn_labels[i],
                                            index=default_idx)
            sel = stations_in_region[selected_idx]
            stn_id = sel[0]
            stn_name = sel[1]
            stn_start = sel[2]
            st.caption(f"[ASOS] {stn_name} ({region}) · 관측 가능일: {stn_start} ~ 현재")
        else:
            # AWS: API 대신 기상자료개방포털 CSV 업로드 방식
            region = "—"
            stn_id = None
            stn_start = "2000-01-01"   # 기간선택 위젯이 깨지지 않도록 두는 더미 값

            st.caption(
                "기상청 API는 단일 시점 조회만 지원하여 장기 분석이 불가합니다. "
                "[기상자료개방포털](https://data.kma.go.kr)에서 CSV를 직접 다운로드 후 "
                "아래에 업로드하면 동일한 분석이 가능합니다."
            )
            with st.expander("CSV 다운로드 방법"):
                st.markdown(
                    "1. [기상자료개방포털](https://data.kma.go.kr) 접속  \n"
                    "2. **기후통계분석 → 방재기상관측 → 시간자료**  \n"
                    "3. 관측소·기간 선택 후 **CSV 다운로드**  \n"
                    "4. 연도별로 나눠 받은 경우 여러 파일을 동시에 업로드 가능  \n"
                    "5. 컬럼에 **풍향(deg)** 과 **풍속(m/s)** 이 포함된 파일이어야 합니다."
                )
            stn_name = st.text_input("관측소 이름 (차트 표시용)", value="AWS 관측소")
            aws_files = st.file_uploader(
                "AWS 시간자료 CSV (복수 파일 동시 업로드 가능)",
                type=["csv"],
                accept_multiple_files=True,
                key="aws_csv",
            )
            if aws_files:
                st.caption(f"{len(aws_files)}개 파일 업로드됨")

        st.markdown("---")
        st.markdown("**주소로 가까운 관측소 검색**")
        st.caption(
            "주소를 입력하면 종관(ASOS)·방재(AWS) 관측소 중 가장 가까운 3개소를 각각 찾아줍니다. "
            "(기상청 API 허브 인증키·카카오 REST API 키는 상단 'API 키 설정'에서 입력)"
        )
        addr_input = st.text_input("주소 입력", placeholder="예: 대구 동구 동대구로 550")

        if st.button("가까운 관측소 검색", key="btn_addr_search"):
            _kma_hub_key = st.session_state.get("kma_hub_key", "")
            _kakao_key = st.session_state.get("kakao_key", "")
            if not _kma_hub_key or not _kakao_key:
                st.error("'API 키 설정' 팝업에서 기상청 API 허브 인증키와 카카오 REST API 키를 먼저 입력하세요.")
            elif not addr_input:
                st.error("주소를 입력하세요.")
            else:
                with st.spinner("주소 검색 중..."):
                    lat, lon, disp_addr, err = _geocode_address_kakao(addr_input, _kakao_key)
                if err:
                    st.error(f"주소 검색 실패: {err}")
                else:
                    st.success(f"검색 위치: {disp_addr}  ({lat:.5f}, {lon:.5f})")
                    with st.spinner("관측소 DB 로딩 중..."):
                        try:
                            stn_db = _load_station_db(_kma_hub_key)
                        except Exception as e:
                            stn_db = None
                            st.error(f"관측소 DB 로딩 실패: {e}")

                    if stn_db is not None and len(stn_db) > 0:
                        near_asos = _nearest_stations(lat, lon, stn_db, 'ASOS', n=3)
                        near_aws  = _nearest_stations(lat, lon, stn_db, 'AWS', n=3)

                        _disp_cols = {'stn_id': '지점번호', 'name_ko': '관측소명',
                                      'dist_km': '거리(km)', 'addr': '주소'}

                        st.markdown("**종관(ASOS) 최근접 3개소**")
                        st.dataframe(
                            near_asos[list(_disp_cols)].rename(columns=_disp_cols)
                                .style.format({'거리(km)': '{:.2f}'}),
                            hide_index=True, width='stretch',
                        )
                        st.markdown("**방재(AWS) 최근접 3개소**")
                        st.dataframe(
                            near_aws[list(_disp_cols)].rename(columns=_disp_cols)
                                .style.format({'거리(km)': '{:.2f}'}),
                            hide_index=True, width='stretch',
                        )
                        st.caption(
                            "ASOS는 위 '관측소 선택'에서 해당 지점을 고르세요. "
                            "AWS는 기상자료개방포털에서 해당 관측소명으로 CSV를 다운로드해 업로드하세요."
                        )

with row1_col2:
    with st.container(border=True):
        st.markdown("**2. 분석 기간**")
        preset = st.radio(
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

            cA, cB = st.columns(2)
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
            st.error("시작이 종료보다 늦습니다.")
        elif _months < 60:
            st.warning(f"{_months}개월 (<5년) — ICAO 권고 기간 미달")
            st.caption(f"{start_date:%Y-%m} ~ {end_date:%Y-%m} · {_months}개월")
        else:
            st.success(f"{start_date:%Y-%m} ~ {end_date:%Y-%m} · {_months}개월 ({_months/12:.1f}년)")

row2_col1, row2_col2 = st.columns(2)

with row2_col1:
    with st.container(border=True):
        st.markdown("**3. API 키**")
        api_key = st.session_state.get("api_key", "")
        kma_hub_key = st.session_state.get("kma_hub_key", "")
        kakao_key = st.session_state.get("kakao_key", "")

        _key_rows = [
            ("ASOS API Key", api_key),
            ("기상청 API 허브 인증키", kma_hub_key),
            ("카카오 REST API 키", kakao_key),
        ]
        for _label, _val in _key_rows:
            st.caption(f"{'✓' if _val else '○'} {_label} · {'설정됨' if _val else '미설정'}")

        if st.button("API 키 설정", use_container_width=True):
            _api_key_dialog()

with row2_col2:
    with st.container(border=True):
        st.markdown("**4. 측풍 허용치 (ICAO Doc. 9157)**")
        rwy_length = st.number_input("활주로 길이 (m)", min_value=300, max_value=5000, value=2000, step=100)
        low_friction = st.checkbox("종방향 마찰계수 부족 (활주로 제동효과 불량)", value=False)
        auto_limit, auto_note = select_limit_by_rwy_length(rwy_length, low_friction)
        st.caption(f"자동 선택: **{auto_limit} kt** · {auto_note}")
        override = st.checkbox("수동 선택 사용", value=False)
        if override:
            primary_limit = st.selectbox("측풍 허용치 (Knot)", CROSSWIND_LIMITS_KT,
                                         index=CROSSWIND_LIMITS_KT.index(auto_limit))
        else:
            primary_limit = auto_limit

btn_col1, btn_col2 = st.columns([4, 1])
with btn_col1:
    run_clicked = st.button("분석 시작", type="primary", use_container_width=True)
with btn_col2:
    if st.button("데이터 캐시 삭제", use_container_width=True):
        st.cache_data.clear()
        st.info("캐시가 삭제되었습니다.")

st.divider()

# 3. 분석 실행
if run_clicked:
    df = None
    row_count = None
    _chart_start = start_date
    _chart_end   = end_date

    # ── 데이터 수집 ─────────────────────────────────────────────
    if is_asos:
        if not api_key:
            st.error("API Key를 입력하세요.")
        else:
            df, df_invalid_rows, result = get_weather_data_v28(api_key, stn_id, start_date, end_date)
            if df is None:
                st.error(f"분석 실패: {result}")
            else:
                row_count = result
    else:
        # AWS CSV 업로드 경로
        if not aws_files:
            st.error("사이드바에서 AWS 시간자료 CSV 파일을 업로드하세요.")
        else:
            df, df_invalid_rows, result, (csv_s, csv_e) = _parse_aws_csv(aws_files)
            if df is None:
                st.error(f"CSV 파싱 실패: {result}")
            else:
                row_count = result
                if csv_s and csv_e:
                    _chart_start, _chart_end = csv_s, csv_e

    # ── 분석 & 표시 (ASOS / AWS 공통) ───────────────────────────
    if df is not None:

        _period_months = (
            (_chart_end.year - _chart_start.year) * 12
            + (_chart_end.month - _chart_start.month) + 1
        )
        st.success(
            f"{stn_name} · {row_count:,}시간 수집 완료 "
            f"· 실제 분석 기간: **{_chart_start:%Y-%m-%d} ~ {_chart_end:%Y-%m-%d}** "
            f"({_period_months}개월)"
        )
        with st.spinner("바람성분 vector 분석 중..."):
            A = analyze_runway(df)

            # --- 데이터 요약 ---
            st.divider()
            s0, s1, s2, s3, s4 = st.columns(5)
            s0.metric("분석 기간", f"{_chart_start:%Y-%m}", f"~ {_chart_end:%Y-%m}")
            s1.metric("전체 관측 시간", f"{A['N_total']:,} h")
            s2.metric("Calm (0~3 kt)", f"{A['N_calm']:,} h", f"{A['calm_pct']:.2f}%")
            s3.metric("유효 데이터", f"{A['N_eff']:,} h")
            s4.metric("적용 측풍 허용치", f"{primary_limit} kt")
            st.caption("※ Calm(무영향) 데이터는 논문 §3.2에 따라 활주로 방향 무관하게 '이용 가능'으로 집계됩니다.")

            # --- 주 결과(자동/수동 선택된 한계치) ---
            st.subheader(f"분석 결과 · 허용치 {primary_limit} kt")
            r = A['results'][primary_limit]
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("최적 활주로", rwy_name(r['best_angle']), f"{r['best_angle']}°")
            c2.metric("최대 이용률", f"{r['best_usab']:.3f}%",
                      "PASS" if r['pass'] else "FAIL")
            c3.metric("평균 측풍", f"{r['mean_xwind']:.2f} kt")
            c4.metric("동율 후보", f"{r['tied_count']}개",
                      "동율 처리 적용" if r['tied_count'] > 1 else "유일")

            if not r['pass']:
                st.warning(
                    f"단일 활주로로 95% 미달. 2개 활주로 최적 조합: "
                    f"**{rwy_name(r['pair_angles'][0])} + {rwy_name(r['pair_angles'][1])}** "
                    f"→ 이용률 **{r['pair_usab']:.3f}%** "
                    f"{'PASS' if r['pair_pass'] else '여전히 FAIL'}"
                )

            # --- 탭 ---
            t1, t2, t3, t4, t5, t6 = st.tabs([
                "3개 허용치 종합", "이용률 곡선", "바람장미",
                "16방위 빈도표", "2개 활주로 분석", "방위각 상세표"
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
                        "단일 판정": "PASS" if rr['pass'] else "FAIL",
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
                # ── 바람장미 집계: 16방위 × 6풍속구간 → 빈도(%) ──────────
                _wd_r  = df['wd'].to_numpy(dtype=np.float32)
                _ws_r  = df['ws_kt'].to_numpy(dtype=np.float32)
                _N_r   = len(_wd_r)

                # 16방위 bin (22.5° 간격, N=0°)
                _dir_ang  = np.arange(0, 360, 22.5)                    # [0, 22.5 … 337.5]
                _dir_idx  = ((((_wd_r + 11.25) // 22.5) % 16)).astype(np.int32)

                # 풍속 구간 6단계 (kt): (0,3], (3,7], … >21
                _spd_labels = ["0–3 kt", "3–7 kt", "7–11 kt",
                               "11–17 kt", "17–21 kt", "≥21 kt"]
                _spd_thresh = [3, 7, 11, 17, 21]                        # 오름차순 경계값
                _spd_idx = np.zeros(_N_r, dtype=np.int32)
                for _i, _t in enumerate(_spd_thresh):
                    _spd_idx[_ws_r > _t] = _i + 1                      # 초과(>) 기준 bin 배정

                # 집계 (16 × 6) → 전체 관측 대비 %
                _rose_rows = []
                for _d in range(16):
                    for _s in range(6):
                        _cnt = int(((_dir_idx == _d) & (_spd_idx == _s)).sum())
                        _rose_rows.append({
                            'angle':     float(_dir_ang[_d]),
                            'speed_bin': _spd_labels[_s],
                            'freq_pct':  _cnt / _N_r * 100.0,
                        })
                _df_rose = pd.DataFrame(_rose_rows)

                # 이산 색상 (오름차순: 연한색 → 진한색)
                _color_map = {
                    "0–3 kt":   "#c6dbef",   # 연한 하늘색 (calm)
                    "3–7 kt":   "#74c476",   # 연두
                    "7–11 kt":  "#fdd835",   # 노랑
                    "11–17 kt": "#fd8d3c",   # 주황
                    "17–21 kt": "#e31a1c",   # 빨강
                    "≥21 kt":   "#67000d",   # 암적색 (강풍)
                }

                fig2 = px.bar_polar(
                    _df_rose,
                    r="freq_pct",
                    theta="angle",
                    color="speed_bin",
                    color_discrete_map=_color_map,
                    category_orders={"speed_bin": _spd_labels},
                    title=f"Wind Rose — {stn_name}  ({_chart_start:%Y-%m} ~ {_chart_end:%Y-%m})",
                    template="plotly_white",
                )
                fig2.update_layout(
                    polar=dict(
                        angularaxis=dict(
                            tickmode="array",
                            tickvals=[0, 45, 90, 135, 180, 225, 270, 315],
                            ticktext=["N", "NE", "E", "SE", "S", "SW", "W", "NW"],
                            direction="clockwise",
                            rotation=90,           # N을 12시 방향으로
                        ),
                        radialaxis=dict(
                            ticksuffix="%",        # 반경 축 단위 (%)
                            angle=45,              # 눈금 레이블 겹침 방지
                            tickangle=45,
                        ),
                    ),
                    legend=dict(title="풍속 구간", traceorder="normal"),
                    margin=dict(t=60, b=30, l=30, r=30),
                    height=540,
                )
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
                          "PASS" if r['pair_pass'] else "FAIL")
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
                st.markdown("##### 허용치별 최적 방위각 (표 기준)")
                best_rows = []
                for lim in CROSSWIND_LIMITS_KT:
                    sub = df_table[["방향 (°)", "대응방향 (°)", "활주로", f"{lim} kt 이용률 (%)"]]
                    top = sub.loc[sub[f"{lim} kt 이용률 (%)"].idxmax()]
                    best_rows.append({
                        "허용치": f"{lim} kt",
                        "최적 방향": f"{int(top['방향 (°)'])}° / {int(top['대응방향 (°)'])}°",
                        "활주로": top['활주로'],
                        "이용률 (%)": f"{top[f'{lim} kt 이용률 (%)']:.2f}",
                        "판정": "PASS" if top[f'{lim} kt 이용률 (%)'] >= USABILITY_TARGET else "FAIL",
                    })
                st.dataframe(pd.DataFrame(best_rows), width='stretch', hide_index=True)

                # CSV 다운로드
                csv_bytes = df_table.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
                st.download_button(
                    "CSV 다운로드",
                    csv_bytes,
                    file_name=f"runway_usability_{stn_name}_{_chart_start}_{_chart_end}_step{step}.csv",
                    mime="text/csv",
                )

            # ── 데이터 품질 검토 ───────────────────────────────────────
            st.divider()
            st.subheader("데이터 품질 검토")

            _n_valid   = A['N_total']
            _n_invalid = len(df_invalid_rows) if df_invalid_rows is not None else 0
            _n_raw     = _n_valid + _n_invalid
            _valid_pct = _n_valid   / _n_raw * 100 if _n_raw > 0 else 0
            _miss_pct  = _n_invalid / _n_raw * 100 if _n_raw > 0 else 0

            qa1, qa2, qa3 = st.columns(3)
            qa1.metric("전체 수집 행",          f"{_n_raw:,} 행")
            qa2.metric("유효 데이터 (풍향+풍속 존재)", f"{_n_valid:,} 행",   f"{_valid_pct:.1f}%")
            qa3.metric("결측 데이터 (풍향 또는 풍속 없음)", f"{_n_invalid:,} 행", f"{_miss_pct:.1f}%")

            st.caption(
                "**유효**: 풍향(°)과 풍속(m/s) 값이 모두 관측된 시각 → 분석에 사용됨  \n"
                "**결측**: 풍향 또는 풍속이 누락된 시각 (장비 오류·통신 두절 등) → 분석에서 제외됨"
            )

            # Excel 2-시트 다운로드 (유효 / 결측)
            _excel_buf = io.BytesIO()
            # 유효 데이터: 주요 컬럼만 선별해 가독성 확보
            _valid_export_cols = [c for c in ['tm', 'wd', 'ws', 'ws_kt'] if c in df.columns]
            _valid_export = df[_valid_export_cols].copy() if _valid_export_cols else df.copy()
            _rename_map = {'tm': '관측시각', 'wd': '풍향(°)', 'ws': '풍속(m/s)', 'ws_kt': '풍속(kt)'}
            _valid_export.rename(columns=_rename_map, inplace=True)

            with pd.ExcelWriter(_excel_buf, engine='openpyxl') as _writer:
                _valid_export.to_excel(_writer, sheet_name='유효_데이터', index=False)
                if _n_invalid > 0:
                    _inv_export = df_invalid_rows.copy()
                    _inv_export.rename(columns=_rename_map, inplace=True)
                    _inv_export.to_excel(_writer, sheet_name='결측_데이터', index=False)
                else:
                    pd.DataFrame({"안내": ["결측 데이터가 없습니다."]}).to_excel(
                        _writer, sheet_name='결측_데이터', index=False
                    )

            st.download_button(
                "데이터 품질 보고서 다운로드 (Excel)",
                _excel_buf.getvalue(),
                file_name=f"data_quality_{stn_name}_{_chart_start}_{_chart_end}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
