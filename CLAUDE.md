# 활주로 이용률 정밀 분석 — CLAUDE.md

## 프로젝트 개요

KMA ASOS 시간 관측 데이터를 기반으로 활주로 측풍 이용률과 풍배도를 분석하는 **Streamlit 단일 파일 앱**.

- 메인 파일: `app.py` (전체 로직, UI, 분석 모두 포함)
- 배포: Streamlit Community Cloud (`kimjisu04191-netizen/runway-wind-analysis` GitHub repo — **PUBLIC**)
- 로컬 미리보기 포트: 8513

---

## 보안 — 절대 위반 금지

**API 키를 코드에 하드코딩하는 것은 퍼블릭 레포이므로 절대 금지.**

키 3개는 오직 두 곳에서만 관리된다:
1. `.streamlit/secrets.toml` — 로컬 전용, `.gitignore`에 등록됨, GitHub에 절대 올라가지 않음
2. `st.session_state` — 런타임 세션 한정 보관, `_secret()` 헬퍼로 로드

```
ASOS_API_KEY   → st.secrets["ASOS_API_KEY"]  (data.go.kr, AsosHourlyInfoService)
KMA_HUB_KEY    → st.secrets["KMA_HUB_KEY"]   (apihub.kma.go.kr, stn_inf.php)
KAKAO_REST_KEY → st.secrets["KAKAO_REST_KEY"] (dapi.kakao.com, 주소→위경도)
```

코드 수정 후 git push 전에 반드시 `security-guardian` 서브에이전트를 실행하거나,
secrets.toml의 실제 키 값이 코드에 들어갔는지 다음 명령으로 수동 확인한다
(키 값을 추적 파일에 남기지 않도록, 비교 대상은 secrets.toml에서 읽어온다):

```bash
grep -oE '[A-Za-z0-9+/=_-]{15,}' .streamlit/secrets.toml \
  | while IFS= read -r k; do grep -qF "$k" app.py && echo "[유출] $k"; done
# 아무 출력도 없으면 정상
```

---

## 핵심 상수 (app.py 493~528번 줄)

```python
CROSSWIND_LIMITS_KT = [10, 13, 20]   # ICAO Doc.9157 Table 1 허용치 3종
CALM_THRESHOLD_KT   = 3.0            # 분석 제외 기준 (0~3 kt → Calm)
KT_TO_MS            = 1 / 1.94384    # kt → m/s 변환 계수
RWY_ANGLE_STEP_DEG  = 10             # 분석 격자 (10° × 18개 방향)
_CALM_ROSE_KT       = 0.5 * 1.94384 # 풍배도 Calm 원: 0.5 m/s ≈ 0.97 kt
```

---

## 분석 방법론

### 활주로 이용률 계산 (ICAO Doc.9157)

```
usability = (N_calm + N_eff_covered) / N_total × 100
```

- `N_calm`: 풍속 ≤ 3 kt 관측 수 (무영향 → 전 방향 유효)
- `N_eff_covered`: 측풍 성분 ≤ 허용치인 관측 수
- 허용치 3종(10/13/20 kt)을 **동시에 고려해 단일 최적 각도**를 선정 (조인트 최적화)

### 최적 각도 선정 (조인트 방식)

```python
combined_usab = sum(usab_by_limit[l] for l in CROSSWIND_LIMITS_KT)
best_idx = np.argmax(combined_usab)           # 배열 인덱스 (0~17)
joint_best_angle = int(angles[best_idx])      # 실제 각도 (0°~170°)
```

**주의**: `best_idx`(배열 인덱스)와 `joint_best_angle`(실제 각도°)는 다르다.
- `angles = np.arange(0, 180, 10)` → index 5 = 50°, index 17 = 170°
- `usability[idx]` 접근 시 인덱스 사용, `rwy_name(angle)` 등 표시 시 각도 사용
- t6 상세표: `idx = i // RWY_ANGLE_STEP_DEG` (i는 10, 20, ..., 180)

### 16방위 빈도표 속도 구간

```python
speed_thresh = [3, 10, 13, 20]   # 초과(>) 기준 → 빈틈 없는 구간
# Calm: ws <= 3, 구간1: ws > 3 and ws <= 10, ...
```
`ws >= lo and ws <= hi` 방식은 정수 경계에서 소수점 값이 누락되어 합계가 100%가 되지 않으므로 사용 금지.

---

## UI 구조

### 레이아웃

```
[제목 활주로 이용률 정밀 분석]  [API 키 설정 버튼]
┌─────────────────────────┬─────────────────────────────────┐
│ 1. 관측소 선택 (지역/주소) │ 2. 분석기간  (날짜 범위)          │
│                         │ 3. 측풍 허용치 (auto or 수동)     │
└─────────────────────────┴─────────────────────────────────┘
[분석 시작] 버튼
```

### 결과 탭 구조

| 탭 변수 | 내용 |
|---------|------|
| t1 | 3개 허용치 종합 표 (허용치/이용률/평균측풍 kt/평균측풍 m/s/최대측풍 kt/최대측풍 m/s) |
| t2 | 이용률 곡선 (각도 vs 이용률 %, 3개 허용치 선) |
| t3 | 풍배도 (바람장미, 16방위, 속도 구간별 색상, 중앙 Calm 원) |
| t4 | 16방위 빈도표 |
| t5 | 2개 활주로 최적 조합 (pair analysis) |
| t6 | 방위각 상세표 (10° 격자 고정, 인터벌 선택 없음) |

---

## 풍속 표기 규칙

**모든 분석 결과에서 kt와 m/s를 동시에 표기한다.**

```python
def fmt_kt(kt, decimals=1):
    return f"{kt:g} kt ({kt * KT_TO_MS:.{decimals}f} m/s)"

# 예시
fmt_kt(20)  → "20 kt (10.3 m/s)"
fmt_kt(3.0) → "3 kt (1.5 m/s)"
```

속도 구간 레이블 예: `"0–3 kt (0–1.5 m/s)"`, `"3–10 kt (1.5–5.1 m/s)"`

---

## API 명세

### ASOS 시간 자료 (data.go.kr)

```
URL: https://apis.data.go.kr/1360000/AsosHourlyInfoService/getWthrDataList
인증: serviceKey (Decoding 키, URL 인코딩 금지)
응답: JSON, numOfRows=999
주요 필드: wd (풍향 °), ws (풍속 kt), ta, rn1
```

### KMA API Hub — 관측소 DB (apihub.kma.go.kr)

```
URL: https://apihub.kma.go.kr/api/typ01/url/stn_inf.php
인증: authKey
인코딩: EUC-KR 고정폭 텍스트 → 반드시 바이트 단위 슬라이싱
SFC(ASOS): stn_id[0:5] lon[5:19] lat[19:33] name_ko[96:117] addr[163:222]
AWS:        stn_id[0:5] lon[5:19] lat[19:33] name_ko[71:92]  addr[138:197]
캐시: @st.cache_data(ttl=86400)
```

### Kakao Local API (dapi.kakao.com)

```
URL: https://dapi.kakao.com/v2/local/search/address.json
헤더: Authorization: KakaoAK {kakao_key}
파라미터: query=주소키워드
응답: documents[0].x(경도), documents[0].y(위도)
```

---

## 자주 쓰는 명령어

```bash
# 로컬 실행
python -m streamlit run app.py --server.headless true --server.port 8513

# 문법 검사
python -c "import ast; ast.parse(open('app.py', encoding='utf-8').read()); print('OK')"

# API 키 하드코딩 검사 (push 전 필수 — secrets.toml의 키 값이 코드에 들어갔는지)
grep -oE '[A-Za-z0-9+/=_-]{15,}' .streamlit/secrets.toml \
  | while IFS= read -r k; do grep -qF "$k" app.py && echo "[유출] $k"; done

# GitHub 배포 (push 시 Streamlit Cloud 자동 반영)
git add app.py && git commit -m "설명" && git push origin main
```

---

## 스타일 규칙

- 이모지 없음 (전체 앱에서 사용 금지)
- 주석은 이유(WHY)가 비자명할 때만 — WHAT 설명 주석 금지
- 새 기능 추가 시 관련 없는 코드 정리나 리팩터링 금지 (최소 변경)
- `st.secrets`는 항상 `_secret()` 헬퍼를 통해 접근 (KeyError 방지)

---

## 서브에이전트 위임 규칙

| 상황 | 호출할 서브에이전트 |
|------|-------------------|
| `git push` 또는 `git commit` 직전 | `security-guardian` |
| `app.py` 편집 완료 후 | `streamlit-verifier` |
| `analyze_runway()` 또는 `_build_freq_table()` 변경 시 | `wind-calc-verifier` |
